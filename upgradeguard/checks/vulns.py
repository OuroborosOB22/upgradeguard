import json
import os
import re
import sys

from ..graph import TOOLING_PACKAGES
from ..spec import canonical_name
from ..util import run_command, write_json

FALLBACK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "advisories.json")


def version_key(text):
    parts = re.findall(r"\d+", text or "")
    return tuple(int(part) for part in parts[:4]) or (0,)


def audit_environment(site_packages, output_dir, service="pypi", timeout=600, allow_network=True):
    raw_path = os.path.join(output_dir, "audit.json")
    if allow_network and site_packages:
        result = run_command(
            [
                sys.executable, "-m", "pip_audit",
                "--path", site_packages,
                "--format", "json",
                "--progress-spinner", "off",
                "--vulnerability-service", service,
            ],
            log_path=os.path.join(output_dir, "audit.log"),
            timeout=timeout,
        )
        parsed = safe_parse(result["output"])
        if parsed is not None:
            findings = normalise_pip_audit(parsed)
            write_json(raw_path, parsed)
            return {
                "source": "pip-audit",
                "service": service,
                "available": True,
                "findings": findings,
                "raw_path": raw_path,
            }

    findings = fallback_scan(site_packages)
    write_json(raw_path, {"source": "bundled-advisories", "findings": findings})
    return {
        "source": "bundled-advisories",
        "service": "offline",
        "available": False,
        "findings": findings,
        "raw_path": raw_path,
    }


def safe_parse(text):
    stripped = text.strip()
    start = stripped.find("{")
    if start < 0:
        return None
    try:
        return json.loads(stripped[start:])
    except ValueError:
        return None


def normalise_pip_audit(payload):
    findings = []
    seen = set()
    for dependency in payload.get("dependencies", []):
        name = canonical_name(dependency.get("name", ""))
        if name in TOOLING_PACKAGES:
            continue
        version = dependency.get("version", "")
        for vulnerability in dependency.get("vulns", []):
            identifier = vulnerability.get("id", "")
            key = (name, version, identifier)
            if key in seen:
                continue
            seen.add(key)
            findings.append({
                "package": name,
                "version": version,
                "id": identifier,
                "aliases": vulnerability.get("aliases", []),
                "fix_versions": vulnerability.get("fix_versions", []),
                "summary": (vulnerability.get("description") or "").strip().split("\n")[0][:300],
            })
    return sorted(findings, key=lambda item: (item["package"], item["id"]))


def fallback_scan(site_packages):
    if not os.path.isfile(FALLBACK_FILE) or not site_packages:
        return []
    with open(FALLBACK_FILE) as handle:
        advisories = json.load(handle).get("advisories", [])

    from ..metadata import read_installed_packages
    env_dir = os.path.dirname(os.path.dirname(os.path.dirname(site_packages)))
    installed = {package.canonical: package.version for package in read_installed_packages(env_dir)}

    findings = []
    for advisory in advisories:
        name = canonical_name(advisory.get("package", ""))
        if name not in installed or name in TOOLING_PACKAGES:
            continue
        current = installed[name]
        if version_key(current) < version_key(advisory.get("fixed_in", "0")):
            findings.append({
                "package": name,
                "version": current,
                "id": advisory.get("id", ""),
                "aliases": advisory.get("aliases", []),
                "fix_versions": [advisory.get("fixed_in", "")],
                "summary": advisory.get("summary", ""),
            })
    return sorted(findings, key=lambda item: (item["package"], item["id"]))


def diff_vulnerabilities(before, after):
    before_ids = {(item["package"], item["id"]) for item in before.get("findings", [])}
    after_index = {(item["package"], item["id"]): item for item in after.get("findings", [])}
    before_index = {(item["package"], item["id"]): item for item in before.get("findings", [])}

    introduced = [after_index[key] for key in sorted(set(after_index) - before_ids)]
    resolved = [before_index[key] for key in sorted(before_ids - set(after_index))]
    remaining = [after_index[key] for key in sorted(set(after_index) & before_ids)]
    return {
        "introduced": introduced,
        "resolved": resolved,
        "remaining": remaining,
        "before_count": len(before_index),
        "after_count": len(after_index),
    }
