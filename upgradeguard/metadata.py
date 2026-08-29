import glob
import os
from dataclasses import dataclass, field, asdict
from email.parser import Parser

from .spec import canonical_name


@dataclass
class InstalledPackage:
    name: str
    canonical: str
    version: str
    requires: list = field(default_factory=list)
    license_raw: str = ""
    license_source: str = ""
    classifiers: list = field(default_factory=list)
    metadata_path: str = ""

    def to_dict(self):
        return asdict(self)


def site_packages_dir(env_dir):
    matches = glob.glob(os.path.join(env_dir, "lib", "python*", "site-packages"))
    if matches:
        return matches[0]
    windows = os.path.join(env_dir, "Lib", "site-packages")
    if os.path.isdir(windows):
        return windows
    return ""


def read_installed_packages(env_dir):
    target = site_packages_dir(env_dir)
    if not target:
        return []
    packages = []
    for info_dir in sorted(glob.glob(os.path.join(target, "*.dist-info"))):
        metadata_file = os.path.join(info_dir, "METADATA")
        if not os.path.isfile(metadata_file):
            continue
        packages.append(parse_metadata_file(metadata_file))
    return [package for package in packages if package.name]


def parse_metadata_file(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        message = Parser().parse(handle, headersonly=True)

    name = (message.get("Name") or "").strip()
    version = (message.get("Version") or "").strip()
    requires = [value.strip() for value in message.get_all("Requires-Dist") or []]
    classifiers = [value.strip() for value in message.get_all("Classifier") or []]

    license_raw = ""
    license_source = ""
    expression = (message.get("License-Expression") or "").strip()
    if expression:
        license_raw = expression
        license_source = "License-Expression"
    else:
        legacy = (message.get("License") or "").strip()
        if legacy and len(legacy) < 200:
            license_raw = legacy
            license_source = "License"
    if not license_raw:
        for classifier in classifiers:
            if classifier.startswith("License ::"):
                license_raw = classifier
                license_source = "Classifier"
                break

    return InstalledPackage(
        name=name,
        canonical=canonical_name(name),
        version=version,
        requires=requires,
        license_raw=license_raw,
        license_source=license_source,
        classifiers=classifiers,
        metadata_path=path,
    )


def packages_as_map(packages):
    return {package.canonical: package for package in packages}
