import hashlib
import os
import platform
import re
import time

from .spec import canonical_name
from .util import write_json
from .verdict import ACCEPT, INSUFFICIENT, REJECT

SCHEMA_VERSION = "1.0.0"
VERDICT_NAMES = {ACCEPT: "ACCEPT", REJECT: "REJECT", INSUFFICIENT: "INSUFFICIENT_EVIDENCE"}
SEVERITY_NAMES = {"blocking": "BLOCKING", "warning": "WARNING", "info": "INFO"}
TEST_OUTCOMES = {"passed": "PASS", "failed": "FAIL", "error": "ERROR", "skipped": "SKIP"}
MEDIA_TYPES = {".json": "application/json", ".log": "text/plain", ".txt": "text/plain", ".xml": "application/xml",
               ".html": "text/html", ".gz": "application/gzip"}
SAFE_PATH = re.compile(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*")


def slug(text, minimum=3, maximum=64):
    cleaned = re.sub(r"[^a-z0-9._-]+", "-", str(text).lower()).strip("-._")
    cleaned = (cleaned or "item")[:maximum].strip("-._") or "item"
    return cleaned.ljust(minimum, "x")


def profile_id(pytest_args):
    if not pytest_args:
        return "pytest-default"
    return "pytest-" + hashlib.sha256(" ".join(pytest_args).encode()).hexdigest()[:8]


def environment_block(python_version, allow_network, image_digest=None, names=None):
    return {
        "os": platform.system().lower() or "unknown",
        "architecture": platform.machine() or "unknown",
        "runtimes": {"python": python_version or "unknown"},
        "image_digest": image_digest,
        "network_mode": "CONTROLLED" if allow_network else "OFFLINE",
        "env_var_names": sorted(names or []),
    }


def request_from_parts(run_id, repo_path, source, spec, policy_name, python_version, allow_network,
                       operation="REHEARSE_UPGRADE", execution_provider="LOCAL", image_digest=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": slug(run_id),
        "project_id": slug(os.path.basename(repo_path.rstrip("/"))),
        "operation": operation,
        "source": {key: source[key] for key in ("commit", "dirty", "manifest_sha256", "snapshot_id", "exclusions")},
        "profile_id": profile_id(spec.get("pytest_args", [])),
        "environment_spec": environment_block(python_version, allow_network, image_digest, sorted(spec.get("build_env", {}))),
        "policy_id": slug(policy_name),
        "execution_provider": execution_provider,
        "change": {"ecosystem": "PYTHON", "package": canonical_name(spec["package"]),
                   "from_version": spec["from_version"], "to_version": spec["to_version"]},
    }


def build_request(bundle, operation="REHEARSE_UPGRADE", execution_provider="LOCAL", image_digest=None):
    return request_from_parts(
        bundle["run_id"], bundle["spec"]["repo_path"], bundle["source"], bundle["spec"], bundle["policy"]["name"],
        bundle["before"]["build"].get("python_version", ""), bundle["options"]["allow_network"],
        operation, execution_provider, image_digest)


def media_type(name):
    return MEDIA_TYPES.get(os.path.splitext(name)[1], "application/octet-stream")


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_id(relative):
    text = slug(relative.replace("/", "-"), minimum=1, maximum=100)
    if len(text) <= 64:
        return text
    return text[:55].strip("-._") + "-" + hashlib.sha256(relative.encode()).hexdigest()[:8]


def artifact_manifest(evidence_dir, skip=("evidence.json",)):
    items = []
    for current, folders, names in os.walk(evidence_dir):
        folders.sort()
        for name in sorted(names):
            full = os.path.join(current, name)
            relative = os.path.relpath(full, evidence_dir).replace(os.sep, "/")
            if relative in skip or os.path.islink(full) or not SAFE_PATH.fullmatch(relative):
                continue
            items.append({"id": artifact_id(relative), "path": relative, "sha256": file_sha256(full), "media_type": media_type(name)})
    return items


def stage(outcome, exit_code, seconds, log=None):
    item = {"outcome": outcome, "exit_code": exit_code, "duration_seconds": round(float(seconds or 0), 2)}
    if log:
        item["log_artifact"] = log
    return item


def install_stage(build, side):
    if build["ok"]:
        outcome = "PASS"
    elif build["failure_stage"] in ("venv-create", "dependency-install", "project-install", "test-runner-install"):
        outcome = "FAIL"
    else:
        outcome = "NOT_RUN"
    return stage(outcome, build.get("install_returncode"), build.get("duration"), artifact_id(side + "/install.log"))


def tests_block(tests, side):
    if tests["timed_out"]:
        outcome = "TIMED_OUT"
    elif not tests["ran"]:
        outcome = "NOT_RUN"
    else:
        outcome = "PASS" if tests["returncode"] == 0 else "FAIL"
    results = [{"id": identifier, "outcome": TEST_OUTCOMES.get(entry["status"], "ERROR")} for identifier, entry in sorted(tests["results"].items())]
    return {"stage": stage(outcome, tests["returncode"] if tests["returncode"] >= 0 else None, tests["duration"], artifact_id(side + "/pytest.log")),
            "results": results}


def scanner_records(side_data, checked_at, pip_audit_version):
    vulnerabilities = side_data["vulnerabilities"]
    conflicts = side_data["conflicts"]
    built = side_data["build"]["ok"]
    return [
        {"scanner": "pip-audit" if vulnerabilities["source"] == "pip-audit" else "bundled-advisories",
         "version": pip_audit_version if vulnerabilities["source"] == "pip-audit" else "bundled",
         "available": bool(vulnerabilities["available"]),
         "coverage": "python packages in the environment" if vulnerabilities["available"] else "a small offline advisory list only",
         "checked_at": checked_at, "finding_count": len(vulnerabilities["findings"])},
        {"scanner": "pip-check", "version": "pip", "available": built, "coverage": "installed package requirement consistency",
         "checked_at": checked_at, "finding_count": len(conflicts["problems"])},
        {"scanner": "licence-policy", "version": "1", "available": built, "coverage": "licence text of installed packages",
         "checked_at": checked_at, "finding_count": len(side_data["licenses"]["violations"])},
    ]


def side_block(bundle, side, checked_at, pip_audit_version, manifest_ids):
    data = bundle[side]
    graph = data["graph"]["nodes"]
    return {
        "install": install_stage(data["build"], side),
        "build": stage("NOT_RUN", None, 0),
        "tests": tests_block(data["tests"], side),
        "resolved_dependencies": [{"name": name, "version": node["version"]} for name, node in sorted(graph.items())],
        "scanner_results": scanner_records(data, checked_at, pip_audit_version),
        "artifacts": sorted(identifier for identifier in manifest_ids if identifier.startswith(side + "-")),
        "environment": environment_block(data["build"].get("python_version", ""), bundle["options"]["allow_network"]),
    }


def diff_block(diff):
    tests = diff["tests"]
    changed = tests["regressions"]
    return {
        "dependencies": {
            "added": [item["name"] for item in diff["graph"]["added"]],
            "removed": [item["name"] for item in diff["graph"]["removed"]],
            "changed": [{"name": item["name"], "from": item["from_version"], "to": item["to_version"]} for item in diff["graph"]["changed"]],
        },
        "tests": {
            "regressions": [item["test"] for item in changed if item["after"] in ("failed", "error", "not collected")],
            "new_failing": [item["test"] for item in tests["new_failing_tests"]],
            "missing_or_skipped": [item["test"] for item in changed if item["after"] in ("not collected", "skipped")],
        },
    }


def findings_block(verdict, manifest_by_path):
    findings = []
    for source, flag in ((verdict["reasons"], True), (verdict["notes"], False)):
        for item in source:
            evidence = [manifest_by_path[path] for path in item["evidence"] if path in manifest_by_path]
            findings.append({
                "code": item["code"], "severity": SEVERITY_NAMES.get(item["severity"], "INFO"),
                "subject": item["message"][:120], "message": item["message"][:1000],
                "evidence_ids": evidence, "provenance": "upgradeguard verdict rules",
            })
    return findings


def coverage_block(bundle):
    unavailable = []
    checked = ["environment build", "pip check", "licence policy"]
    for side in ("before", "after"):
        if bundle[side]["tests"]["ran"]:
            checked.append("%s tests" % side)
        if not bundle[side]["vulnerabilities"]["available"]:
            unavailable.append("online vulnerability scan (%s)" % side)
    checked.append("vulnerability scan")
    return {"checked": sorted(set(checked)), "not_checked": ["integration tests outside the selected pytest profile", "malware analysis", "runtime behaviour in production"],
            "unavailable": sorted(set(unavailable))}


def pip_audit_version():
    try:
        from importlib.metadata import version
        return version("pip-audit")
    except Exception:
        return "unknown"


def to_contract_evidence(bundle, checked_at, operation="REHEARSE_UPGRADE", execution_provider="LOCAL", image_digest=None):
    manifest = artifact_manifest(bundle["evidence_dir"])
    by_path = {item["path"]: item["id"] for item in manifest}
    ids = [item["id"] for item in manifest]
    version = pip_audit_version()
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": slug(bundle["run_id"]),
        "request": build_request(bundle, operation, execution_provider, image_digest),
        "before": side_block(bundle, "before", checked_at, version, ids),
        "after": side_block(bundle, "after", checked_at, version, ids),
        "diff": diff_block(bundle["diff"]),
        "verdict": {"decision": VERDICT_NAMES[bundle["verdict"]["decision"]], "findings": findings_block(bundle["verdict"], by_path)},
        "coverage": coverage_block(bundle),
        "artifact_manifest": manifest,
    }


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_contract_evidence(bundle, evidence_dir, operation="REHEARSE_UPGRADE", execution_provider="LOCAL", image_digest=None):
    evidence = to_contract_evidence(bundle, utc_now(), operation, execution_provider, image_digest)
    write_json(os.path.join(evidence_dir, "evidence.json"), evidence)
    return evidence
