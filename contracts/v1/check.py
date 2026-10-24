import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = Path(__file__).parent
MANIFEST = HERE / "manifest.json"
SCHEMA_NAMES = ["request", "evidence", "prediction_request", "prediction_response", "snapshot", "comparison", "worker_result"]


def load_json(path):
    return json.loads(path.read_text())


def build_registry():
    registry = Registry()
    for name in SCHEMA_NAMES:
        contents = load_json(HERE / ("%s.schema.json" % name))
        registry = registry.with_resource(contents["$id"], Resource.from_contents(contents))
    return registry


def schema_for(fixture_name):
    for name in sorted(SCHEMA_NAMES, key=len, reverse=True):
        if fixture_name.startswith(name):
            return name
    raise ValueError("no schema matches fixture %s" % fixture_name)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_digests():
    return {name + ".schema.json": digest(HERE / (name + ".schema.json")) for name in SCHEMA_NAMES}


def check_fixtures():
    registry = build_registry()
    problems = []
    for folder, should_pass in (("valid", True), ("invalid", False)):
        for path in sorted((HERE / "fixtures" / folder).glob("*.json")):
            name = schema_for(path.name)
            validator = Draft202012Validator(load_json(HERE / (name + ".schema.json")), registry=registry)
            accepted = not list(validator.iter_errors(load_json(path)))
            if accepted != should_pass:
                problems.append("%s/%s: expected %s" % (folder, path.name, "pass" if should_pass else "fail"))
    return problems


def check_manifest():
    recorded = load_json(MANIFEST)["files"]
    return ["%s: digest changed" % name for name, value in current_digests().items() if recorded.get(name) != value]


def write_manifest():
    MANIFEST.write_text(json.dumps({"contract_version": "1.0.0", "status": "draft", "files": current_digests()}, indent=2) + "\n")


def main():
    if "write" in sys.argv:
        write_manifest()
    problems = check_fixtures() + check_manifest()
    for line in problems:
        print(line)
    print("contract v1: %s" % ("ok" if not problems else "%d problem(s)" % len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
