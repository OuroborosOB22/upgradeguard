import os
import time

from .checks.conflicts import check_conflicts, diff_conflicts
from .checks.licenses import check_licenses, diff_licenses
from .checks.vulns import audit_environment, diff_vulnerabilities
from .graph import build_graph, diff_graphs
from .metadata import packages_as_map
from .report import write_report
from .contract import write_contract_evidence
from .source import describe_source
from .spec import declared_names, new_run_id, pin_package, read_requirements, validate_spec
from .tests_run import diff_test_runs, run_test_suite
from .util import write_json
from .venvs import build_environment, copy_repository, resolve_python
from .verdict import decide


def run_upgrade_check(spec, policy, evidence_root="evidence", work_root="work",
                      allow_network=True, use_cache=True, test_timeout=900,
                      install_timeout=1800, strict_licences=False, progress=None,
                      operation="REHEARSE_UPGRADE", execution_provider="LOCAL", image_digest=None):
    started = time.time()
    validate_spec(spec)
    if not spec.run_id:
        spec.run_id = new_run_id(spec) # responsible for creating unique run folders names

    repo_path = os.path.abspath(spec.repo_path)
    requirements_path = os.path.join(repo_path, spec.requirements_file)
    if not os.path.isfile(requirements_path):
        raise FileNotFoundError("no %s found in %s" % (spec.requirements_file, repo_path))

    evidence_dir = os.path.abspath(os.path.join(evidence_root, spec.run_id)) # evidence/<run_id> for json/html logs
    work_dir = os.path.abspath(os.path.join(work_root, spec.run_id)) # work/<run_id> for venvs and repo copies
    os.makedirs(evidence_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    source = describe_source(repo_path)
    python_bin = resolve_python(spec.python_bin) # returns absolute path to python executable
    base_lines = read_requirements(requirements_path) # req.txt
    direct = set(declared_names(base_lines))

    # pin_package modifies the file lines in memory from ver & to ver
    before_lines, before_found = pin_package(base_lines, spec.package, spec.from_version)
    after_lines, after_found = pin_package(base_lines, spec.package, spec.to_version)
    direct.add(spec.normalised_package())

    sides = {}
    for side, lines in (("before", before_lines), ("after", after_lines)):     #loops through before then after
        announce(progress, "building %s environment" % side)
        side_dir = os.path.join(evidence_dir, side)
        env_dir = os.path.join(work_dir, side, "env")
        repo_copy = copy_repository(repo_path, os.path.join(work_dir, side, "repo"))
        build = build_environment(
            side, env_dir, lines, side_dir, python_bin,
            use_cache=use_cache, install_timeout=install_timeout,
            project_dir=repo_copy if spec.install_project else None, build_env=spec.build_env,
        )

        # builds dependency graph and writes graph.json.
        graph = build_graph(build["packages"], direct)
        write_json(os.path.join(side_dir, "graph.json"), graph)

        # if the environment built successfully then  checks following and generates a sum up in summary.json
        conflicts = {"clean": True, "problems": [], "returncode": 0, "log_path": ""}
        vulnerabilities = {"source": "not-run", "findings": [], "available": False, "raw_path": ""}
        licenses = {"policy": policy.name, "entries": [], "violations": [], "unknown": [], "allowed_count": 0}
        tests = {"ran": False, "results": {}, "counts": {}, "returncode": -1, "log_path": "", "junit_path": "", "tail": "", "duration": 0, "timed_out": False}

        if build["created"] and build["installed"]:
            announce(progress, "checking %s environment" % side)
            conflicts = check_conflicts(env_dir, side_dir)
            vulnerabilities = audit_environment(
                build["site_packages"], side_dir, allow_network=allow_network,
            )
            licenses = check_licenses(graph, policy, side_dir)
        if build["ok"]:
            announce(progress, "running tests in %s environment" % side)
            tests = run_test_suite(env_dir, repo_copy, side_dir, timeout=test_timeout, extra_args=spec.pytest_args)

        sides[side] = {
            "repo_copy": repo_copy,
            "build": strip_packages(build),
            "graph": graph,
            "conflicts": conflicts,
            "vulnerabilities": vulnerabilities,
            "licenses": licenses,
            "tests": tests,
        }
        write_json(os.path.join(side_dir, "summary.json"), sides[side])

    announce(progress, "comparing both environments") # diff
    difference = {
        "graph": diff_graphs(sides["before"]["graph"], sides["after"]["graph"]),
        "conflicts": diff_conflicts(sides["before"]["conflicts"], sides["after"]["conflicts"]),
        "vulnerabilities": diff_vulnerabilities(sides["before"]["vulnerabilities"], sides["after"]["vulnerabilities"]),
        "licenses": diff_licenses(sides["before"]["licenses"], sides["after"]["licenses"]),
        "tests": diff_test_runs(sides["before"]["tests"], sides["after"]["tests"]), # spots rregression after
    }

    # & calls decide(bundle) from verdict.py to calculate verdict
    bundle = {
        "run_id": spec.run_id,
        "spec": spec.to_dict(),
        "policy": policy.to_dict(),
        "python_bin": python_bin,
        "source": source,
        "package_was_declared": before_found and after_found,
        "before": sides["before"],
        "after": sides["after"],
        "diff": difference,
        "evidence_dir": evidence_dir,
        "options": {"strict_licences": strict_licences, "allow_network": allow_network},
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started)),
    }
    bundle["verdict"] = decide(bundle)
    bundle["total_seconds"] = round(time.time() - started, 2)

    # writes run.json, diff.json, verdict.json, bundle.json, and report.html.
    write_json(os.path.join(evidence_dir, "run.json"), bundle["spec"])
    write_json(os.path.join(evidence_dir, "policy.json"), bundle["policy"])
    write_json(os.path.join(evidence_dir, "diff.json"), difference)
    write_json(os.path.join(evidence_dir, "verdict.json"), bundle["verdict"])
    write_json(os.path.join(evidence_dir, "bundle.json"), bundle)
    write_report(bundle, os.path.join(evidence_dir, "report.html"))
    write_contract_evidence(bundle, evidence_dir, operation, execution_provider, image_digest)
    announce(progress, "done")
    return bundle


def strip_packages(build):
    copied = dict(build)
    copied.pop("packages", None) # strip out packages list so bundle.json is lighter
    return copied


def announce(progress, message):
    if progress: 
        progress(message)
