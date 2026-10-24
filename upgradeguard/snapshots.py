import hashlib
import os
import shutil
import time

from .contract import SCHEMA_VERSION, artifact_manifest, environment_block, profile_id, slug, TEST_OUTCOMES
from .graph import build_graph
from .source import build_manifest, compare_manifests, describe_source, write_archive
from .spec import declared_names, read_requirements
from .tests_run import run_test_suite
from .util import read_json, write_json
from .venvs import build_environment, copy_repository, resolve_python

PASSING = "PASSING"
STARTING_ONLY = "STARTING_ONLY"
INCONCLUSIVE = "INCONCLUSIVE"


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def eligibility_for(build, tests, verified):
    if not verified:
        return STARTING_ONLY
    if not build["ok"] or not tests["ran"] or tests["timed_out"]:
        return INCONCLUSIVE
    counts = tests["counts"]
    if tests["returncode"] == 0 and counts.get("failed", 0) == 0 and counts.get("error", 0) == 0:
        return PASSING
    return STARTING_ONLY


def records_of_tests(tests):
    return [{"id": identifier, "outcome": TEST_OUTCOMES.get(entry["status"], "ERROR")} for identifier, entry in sorted(tests["results"].items())]


def snapshot_identity(manifest_sha256, profile, records, eligibility):
    digest = hashlib.sha256()
    digest.update(("%s|%s|%s|" % (manifest_sha256, profile, eligibility)).encode())
    for record in records:
        digest.update(("%s=%s;" % (record["id"], record["outcome"])).encode())
    return "snap-" + digest.hexdigest()[:12]


def project_dir(store_root, project_id):
    return os.path.join(store_root, project_id)


def read_index(store_root, project_id):
    path = os.path.join(project_dir(store_root, project_id), "index.json")
    return read_json(path) if os.path.isfile(path) else []


def add_to_index(store_root, project_id, entry):
    entries = [item for item in read_index(store_root, project_id) if item["snapshot_id"] != entry["snapshot_id"]]
    entries.append(entry)
    entries.sort(key=lambda item: item["created_at"])
    write_json(os.path.join(project_dir(store_root, project_id), "index.json"), entries)


def capture_snapshot(repo_path, store_root, python_bin="python3", requirements_file="requirements.txt", pytest_args=None,
                     install_project=False, build_env=None, verify=True, use_cache=True, test_timeout=900,
                     allow_network=True, progress=None):
    repo_path = os.path.abspath(repo_path)
    requirements_path = os.path.join(repo_path, requirements_file)
    if not os.path.isfile(requirements_path):
        raise FileNotFoundError("no %s found in %s" % (requirements_file, repo_path))
    pytest_args = list(pytest_args or [])
    project = slug(os.path.basename(repo_path.rstrip("/")))
    profile = profile_id(pytest_args)
    announce(progress, "describing the source")
    source = describe_source(repo_path)
    manifest = build_manifest(repo_path)

    staging = os.path.join(project_dir(store_root, project), ".staging-%d" % os.getpid())
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    work = os.path.join(staging, "work")
    try:
        lines = read_requirements(requirements_path)
        repo_copy = copy_repository(repo_path, os.path.join(work, "repo"))
        announce(progress, "building the environment")
        build = build_environment("snapshot", os.path.join(work, "env"), lines, os.path.join(staging, "logs"), resolve_python(python_bin),
                                  use_cache=use_cache, project_dir=repo_copy if install_project else None, build_env=build_env or {})
        tests = {"ran": False, "results": {}, "counts": {}, "returncode": -1, "timed_out": False, "duration": 0}
        if build["ok"] and verify:
            announce(progress, "running the tests")
            tests = run_test_suite(os.path.join(work, "env"), repo_copy, os.path.join(staging, "logs"), timeout=test_timeout, extra_args=pytest_args)
        graph = build_graph(build["packages"], set(declared_names(lines)))
        eligibility = eligibility_for(build, tests, verify)
        records = records_of_tests(tests)
        snapshot_id = snapshot_identity(source["manifest_sha256"], profile, records, eligibility)
        final = os.path.join(project_dir(store_root, project), snapshot_id)
        if os.path.isdir(final):
            return read_json(os.path.join(final, "snapshot.json")), True
        shutil.rmtree(work)
        write_archive(repo_path, manifest, os.path.join(staging, "source.tar.gz"))
        write_json(os.path.join(staging, "manifest.json"), {"files": manifest["files"]})
        record = {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "project_id": project,
            "source": {key: source[key] for key in ("commit", "dirty", "manifest_sha256", "snapshot_id", "exclusions")},
            "environment": environment_block(build.get("python_version", ""), allow_network, None, sorted(build_env or {})),
            "resolved_dependencies": [{"name": name, "version": node["version"]} for name, node in sorted(graph["nodes"].items())],
            "tests": {"verified": verify, "ran": tests["ran"], "results": records},
            "profile_id": profile,
            "eligibility": eligibility,
            "artifacts": [],
            "created_at": utc_now(),
        }
        record["artifacts"] = artifact_manifest(staging, skip=("snapshot.json",))
        write_json(os.path.join(staging, "snapshot.json"), record)
        os.replace(staging, final)
        add_to_index(store_root, project, {"snapshot_id": snapshot_id, "created_at": record["created_at"], "eligibility": eligibility,
                                           "profile_id": profile, "manifest_sha256": source["manifest_sha256"]})
        return record, False
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def load_snapshot(store_root, project_id, snapshot_id):
    path = os.path.join(project_dir(store_root, slug(project_id)), snapshot_id, "snapshot.json")
    if not os.path.isfile(path) or "/" in snapshot_id or ".." in snapshot_id:
        raise FileNotFoundError("no snapshot %s for project %s" % (snapshot_id, project_id))
    return read_json(path)


def latest_passing(store_root, project_id, profile=None, exclude=None):
    entries = [item for item in read_index(store_root, project_id) if item["eligibility"] == PASSING
               and item["snapshot_id"] != exclude and (profile is None or item["profile_id"] == profile)]
    return entries[-1]["snapshot_id"] if entries else None


def dependency_changes(old, new):
    before = {item["name"]: item["version"] for item in old["resolved_dependencies"]}
    after = {item["name"]: item["version"] for item in new["resolved_dependencies"]}
    return {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": [{"name": name, "from": before[name], "to": after[name]} for name in sorted(set(before) & set(after)) if before[name] != after[name]],
    }


def changes_in_tests(old, new):
    before = {item["id"]: item["outcome"] for item in old["tests"]["results"]}
    after = {item["id"]: item["outcome"] for item in new["tests"]["results"]}
    broken = {"FAIL", "ERROR"}
    return {
        "newly_failing": sorted(name for name in before if before[name] == "PASS" and after.get(name) in broken),
        "newly_skipped": sorted(name for name in before if before[name] == "PASS" and after.get(name) == "SKIP"),
        "missing": sorted(name for name in before if before[name] == "PASS" and name not in after),
        "fixed": sorted(name for name in before if before[name] in broken and after.get(name) == "PASS"),
        "added": sorted(set(after) - set(before)),
    }


def runtime_changes(old, new):
    changes = []
    for field in ("os", "architecture"):
        if old["environment"][field] != new["environment"][field]:
            changes.append({"field": field, "from": old["environment"][field], "to": new["environment"][field]})
    for name in sorted(set(old["environment"]["runtimes"]) | set(new["environment"]["runtimes"])):
        left, right = old["environment"]["runtimes"].get(name), new["environment"]["runtimes"].get(name)
        if left != right:
            changes.append({"field": "runtime " + name, "from": left, "to": right})
    return changes


def comparison_warnings(old, new, runtime):
    warnings = []
    if any(item["field"] in ("os", "architecture") for item in runtime):
        warnings.append("The two snapshots ran on different hosts, so differences may come from the host and not from the project.")
    if old["profile_id"] != new["profile_id"]:
        warnings.append("The two snapshots used different verification profiles, so the test results are not directly comparable.")
    if old["eligibility"] != PASSING:
        warnings.append("The older snapshot was not a fully passing run, so its test results are only a starting point.")
    if not new["tests"]["ran"] or not old["tests"]["ran"]:
        warnings.append("At least one snapshot has no test results.")
    warnings.append("A changed file or dependency is a lead, not proof of what caused a difference.")
    return warnings


def compare_snapshots(store_root, project_id, old_id, new_id):
    old = load_snapshot(store_root, project_id, old_id)
    new = load_snapshot(store_root, project_id, new_id)
    old_manifest = read_json(os.path.join(project_dir(store_root, slug(project_id)), old_id, "manifest.json"))
    new_manifest = read_json(os.path.join(project_dir(store_root, slug(project_id)), new_id, "manifest.json"))
    runtime = runtime_changes(old, new)
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "COMPARE",
        "project_id": old["project_id"],
        "old_snapshot_id": old_id,
        "new_snapshot_id": new_id,
        "changes": {
            "code": compare_manifests(old_manifest, new_manifest),
            "runtime": runtime,
            "dependencies": dependency_changes(old, new),
            "tests": changes_in_tests(old, new),
        },
        "warnings": comparison_warnings(old, new, runtime),
        "created_at": utc_now(),
    }


def announce(progress, message):
    if progress:
        progress(message)
