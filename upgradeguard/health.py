import json
import re
from concurrent.futures import ThreadPoolExecutor, wait
import urllib.error
import urllib.request
from dataclasses import dataclass

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from .checks.licenses import evaluate_package
from .spec import PACKAGE_PATTERN, canonical_name

MAX_BYTES = 200_000
MAX_SPECS = 400
PYPI_URL = "https://pypi.org/pypi/%s/json"
MAX_METADATA_BYTES = 12_000_000
LOOKUP_WORKERS = 8
LOOKUP_BUDGET_SECONDS = 45
POINTS = {"invalid": 15, "duplicate": 8, "conflict": 20, "licence_denied": 10, "not_on_index": 10}
BANDS = ((90, "Good"), (70, "Fair"), (0, "Poor"))


class BadFile(ValueError):
    pass


@dataclass
class Entry:
    line: int
    raw: str
    name: str = ""
    specifier: str = ""
    marker: str = ""
    valid: bool = True
    problem: str = ""


def parse(text):
    if len(text.encode("utf8", "replace")) > MAX_BYTES:
        raise BadFile("the file is larger than %d bytes" % MAX_BYTES)
    entries, skipped = [], []
    for number, line in enumerate(text.splitlines(), start=1):
        raw = line.split(" #")[0].strip()
        if not raw or raw.startswith("#"):
            continue
        if raw.startswith("-") or "://" in raw.split(";")[0]:
            skipped.append({"line": number, "text": raw[:120]})
            continue
        if len(entries) >= MAX_SPECS:
            raise BadFile("more than %d specifications" % MAX_SPECS)
        try:
            parsed = Requirement(raw)
        except InvalidRequirement as problem:
            entries.append(Entry(number, raw[:200], valid=False, problem=str(problem).splitlines()[0][:160]))
            continue
        entries.append(Entry(number, raw[:200], canonical_name(parsed.name), str(parsed.specifier), str(parsed.marker or "")))
    return entries, skipped


def candidate_versions(specifiers):
    found = set()
    for spec in specifiers:
        for item in spec:
            try:
                base = Version(item.version.replace(".*", ""))
            except InvalidVersion:
                continue
            parts = list(base.release) + [0, 0]
            found.add(base)
            for index in range(len(base.release)):
                for step in (-1, 1):
                    changed = parts[:len(base.release)]
                    changed[index] = max(0, changed[index] + step)
                    found.add(Version(".".join(str(part) for part in changed)))
    found |= {Version("0"), Version("9999")}
    return found


def has_conflict(specifier_texts):
    sets = [SpecifierSet(text) for text in specifier_texts]
    for version in candidate_versions(sets):
        if all(item.contains(version, prereleases=True) for item in sets):
            return False
    return True


def find_duplicates_and_conflicts(entries):
    by_name = {}
    for entry in entries:
        if entry.valid:
            by_name.setdefault((entry.name, entry.marker), []).append(entry)
    duplicates, conflicts = [], []
    for (name, marker), group in sorted(by_name.items()):
        if len(group) < 2:
            continue
        duplicates.append({"package": name, "lines": [item.line for item in group], "declarations": len(group)})
        texts = [item.specifier for item in group if item.specifier]
        if len(texts) > 1 and has_conflict(texts):
            conflicts.append({"package": name, "lines": [item.line for item in group], "requirements": texts})
    return duplicates, conflicts


def fetch_pypi(name, timeout=8):
    if not PACKAGE_PATTERN.fullmatch(name):
        return {"status": "unavailable", "reason": "invalid name"}
    request = urllib.request.Request(PYPI_URL % name, headers={"User-Agent": "upgradeguard-health"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_METADATA_BYTES + 1)
    except urllib.error.HTTPError as problem:
        return {"status": "not_found"} if problem.code == 404 else {"status": "unavailable", "reason": "HTTP %d" % problem.code}
    except (urllib.error.URLError, TimeoutError, OSError) as problem:
        return {"status": "unavailable", "reason": type(problem).__name__}
    if len(raw) > MAX_METADATA_BYTES:
        return {"status": "unavailable", "reason": "response too large"}
    try:
        info = json.loads(raw)["info"]
    except (ValueError, KeyError):
        return {"status": "unavailable", "reason": "unreadable response"}
    classifiers = [item.split("::")[-1].strip() for item in info.get("classifiers") or [] if item.startswith("License ::")]
    licence = info.get("license_expression") or (info.get("license") or "").strip()
    if not licence or len(licence) > 120:
        licence = classifiers[0] if classifiers else ""
    return {"status": "found", "latest": info.get("version") or "", "summary": (info.get("summary") or "")[:200],
            "licence": licence, "requires_python": info.get("requires_python") or ""}


def look_up_all(names, lookup, budget=LOOKUP_BUDGET_SECONDS):
    pool = ThreadPoolExecutor(max_workers=LOOKUP_WORKERS)
    futures = {name: pool.submit(lookup, name) for name in names}
    wait(futures.values(), timeout=budget)
    pool.shutdown(wait=False, cancel_futures=True)
    answers = {}
    for name, future in futures.items():
        answers[name] = future.result() if future.done() and not future.exception() else {"status": "unavailable", "reason": "time budget used up"}
    return answers


def score_for(counts):
    value = 100
    for key, points in POINTS.items():
        value -= counts.get(key, 0) * points
    value = max(0, value)
    return value, next(label for floor, label in BANDS if value >= floor)


def analyse(text, policy, lookup=fetch_pypi):
    entries, skipped = parse(text)
    duplicates, conflicts = find_duplicates_and_conflicts(entries)
    invalid = [{"line": item.line, "text": item.raw, "problem": item.problem} for item in entries if not item.valid]
    names = sorted({item.name for item in entries if item.valid})
    packages, counts = [], {"invalid": len(invalid), "duplicate": len(duplicates), "conflict": len(conflicts), "licence_denied": 0, "not_on_index": 0}
    unknown_licences = metadata_unavailable = 0
    answers = look_up_all(names, lookup)
    for name in names:
        declared = [item for item in entries if item.valid and item.name == name]
        meta = answers[name]
        row = {"package": name, "declared": [item.specifier or "any version" for item in declared], "pinned": any(item.specifier.startswith("==") for item in declared),
               "metadata": meta["status"]}
        if meta["status"] == "found":
            outcome = evaluate_package(name, meta["licence"], policy)
            row.update({"latest": meta["latest"], "summary": meta["summary"], "licence_raw": meta["licence"], "licence": outcome["canonical"],
                        "licence_status": outcome["status"]})
            counts["licence_denied"] += outcome["status"] == "denied"
            unknown_licences += outcome["status"] == "unknown"
        elif meta["status"] == "not_found":
            counts["not_on_index"] += 1
        else:
            metadata_unavailable += 1
            row["reason"] = meta.get("reason", "")
        packages.append(row)
    score, status = score_for(counts)
    reasons = [{"issue": key.replace("_", " "), "count": counts[key], "points_each": POINTS[key], "points": counts[key] * POINTS[key]} for key in POINTS if counts[key]]
    return {
        "total_specifications": len(entries), "valid_specifications": len(entries) - len(invalid), "unique_packages": len(names),
        "invalid": invalid, "duplicates": duplicates, "conflicts": conflicts, "skipped_lines": skipped, "packages": packages,
        "unknown_licences": unknown_licences, "metadata_unavailable": metadata_unavailable, "policy": policy.name,
        "score": score, "status": status, "deductions": reasons,
        "score_note": "Starts at 100. Unknown licences and unavailable metadata are listed, not deducted.",
        "metadata_note": "Package information comes from the public PyPI index at the time of analysis." if not metadata_unavailable else
                         "Package information could not be read for %d packages, so the score covers the file checks and the packages that were found." % metadata_unavailable,
    }
