import os
import re

from .checks.vulns import FALLBACK_FILE, version_key
from .spec import REQUIREMENT_LINE, canonical_name
from .util import read_json
from .verdict import ACCEPT, REJECT

PIP_CHECK = "pip-check"
PIP_AUDIT = "pip-audit"
STATIC_FILE = "static-file"
BASELINE_NAMES = [PIP_CHECK, PIP_AUDIT, STATIC_FILE]


def pip_check_verdict(bundle):
    if not bundle["after"]["build"]["ok"]:
        return REJECT
    return REJECT if bundle["diff"]["conflicts"]["introduced"] else ACCEPT


def pip_audit_verdict(bundle):
    return REJECT if bundle["diff"]["vulnerabilities"]["introduced"] else ACCEPT


def major_part(version):
    match = re.match(r"\s*v?(\d+)", version or "")
    return int(match.group(1)) if match else 0


def known_advisories():
    return read_json(FALLBACK_FILE).get("advisories", [])


def static_file_verdict(package, from_version, to_version, advisories=None):
    advisories = known_advisories() if advisories is None else advisories
    name = canonical_name(package)
    if major_part(to_version) > major_part(from_version):
        return REJECT
    for advisory in advisories:
        if canonical_name(advisory.get("package", "")) != name:
            continue
        if version_key(to_version) < version_key(advisory.get("fixed_in", "0")):
            return REJECT
    return ACCEPT


def pinned_version(requirements_path, package):
    target = canonical_name(package)
    with open(requirements_path) as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "-")):
                continue
            match = REQUIREMENT_LINE.match(stripped)
            if match and canonical_name(match.group(1)) == target and "==" in match.group(3):
                return match.group(3).split("==", 1)[1].split(";")[0].strip()
    return ""


def static_verdict_for_bundle(bundle):
    spec = bundle["spec"]
    before_file = os.path.join(bundle["evidence_dir"], "before", "requirements.used.txt")
    after_file = os.path.join(bundle["evidence_dir"], "after", "requirements.used.txt")
    from_version = pinned_version(before_file, spec["package"]) or spec["from_version"]
    to_version = pinned_version(after_file, spec["package"]) or spec["to_version"]
    return static_file_verdict(spec["package"], from_version, to_version)


def baseline_verdicts(bundle):
    return {
        PIP_CHECK: pip_check_verdict(bundle),
        PIP_AUDIT: pip_audit_verdict(bundle),
        STATIC_FILE: static_verdict_for_bundle(bundle),
    }
