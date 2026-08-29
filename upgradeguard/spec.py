import os
import re
import time
from dataclasses import dataclass, field, asdict

from .util import read_json

REQUIREMENT_LINE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(.*)$")


def canonical_name(name):
    return re.sub(r"[-_.]+", "-", name).strip().lower()


@dataclass
class UpgradeSpec:
    repo_path: str
    package: str
    from_version: str
    to_version: str
    python_bin: str = "python3"
    policy_path: str = ""
    requirements_file: str = "requirements.txt"
    test_command: str = "pytest"
    run_id: str = ""
    label: str = ""

    def normalised_package(self):
        return canonical_name(self.package)

    def to_dict(self):
        return asdict(self)


@dataclass
class LicencePolicy:
    name: str = "default"
    allowed: list = field(default_factory=list)
    denied: list = field(default_factory=list)
    unknown_action: str = "warn"
    package_exceptions: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def new_run_id(spec):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return "%s-%s-%s-to-%s" % (
        stamp,
        spec.normalised_package(),
        spec.from_version.replace(".", "_"),
        spec.to_version.replace(".", "_"),
    )


def load_policy(path):
    if not path:
        return LicencePolicy(
            name="permissive-default",
            allowed=["MIT", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "APACHE-2.0", "ISC", "PSF-2.0", "MPL-2.0", "UNLICENSE"],
            denied=["GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0", "SSPL-1.0"],
            unknown_action="warn",
        )
    raw = read_json(path)
    return LicencePolicy(
        name=raw.get("name", os.path.basename(path)),
        allowed=[value.upper() for value in raw.get("allowed", [])],
        denied=[value.upper() for value in raw.get("denied", [])],
        unknown_action=raw.get("unknown_action", "warn"),
        package_exceptions={canonical_name(k): v for k, v in raw.get("package_exceptions", {}).items()},
    )


def read_requirements(path):
    lines = []
    with open(path) as handle:
        for raw in handle:
            lines.append(raw.rstrip("\n"))
    return lines


def declared_names(lines):
    names = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        match = REQUIREMENT_LINE.match(stripped)
        if match:
            names.append(canonical_name(match.group(1)))
    return names


def pin_package(lines, package, version):
    target = canonical_name(package)
    output = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            output.append(line)
            continue
        match = REQUIREMENT_LINE.match(stripped)
        if match and canonical_name(match.group(1)) == target:
            extras = match.group(2) or ""
            output.append("%s%s==%s" % (match.group(1), extras, version))
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append("%s==%s" % (package, version))
    return output, replaced
