import os
import time

from .checks.conflicts import check_conflicts, diff_conflicts
from .checks.licenses import check_licenses, diff_licenses
from .checks.vulns import audit_environment, diff_vulnerabilities
from .graph import build_graph, diff_graphs
from .metadata import packages_as_map
from .report import write_report
from .spec import declared_names, new_run_id, pin_package, read_requirements
from .tests_run import diff_test_runs, run_test_suite
from .util import write_json
from .venvs import build_environment, resolve_python
from .verdict import decide


def run_upgrade_check(spec, policy, evidence_root="evidence", work_root="work",
                      allow_network=True, use_cache=True, test_timeout=900,
                      install_timeout=1800, progress=None):
    started = time.time()
    if not spec.run_id:
        spec.run_id = new_run_id(spec)

    repo_path = os.path.abspath(spec.repo_path)
    requirements_path = os.path.join(repo_path, spec.requirements_file)
    if not os.path.isfile(requirements_path):
        raise FileNotFoundError("no %s found in %s" % (spec.requirements_file, repo_path))

    evidence_dir = os.path.abspath(os.path.join(evidence_root, spec.run_id))
    work_dir = os.path.abspath(os.path.join(work_root, spec.run_id))
    os.makedirs(evidence_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    python_bin = resolve_python(spec.python_bin)
    base_lines = read_requirements(requirements_path)
    direct = set(declared_names(base_lines))

    before_lines, before_found = pin_package(base_lines, spec.package, spec.from_version)
    after_lines, after_found = pin_package(base_lines, spec.package, spec.to_version)
    direct.add(spec.normalised_package())

    sides = {}
    for side, lines in (("before", before_lines), ("after", after_lines)):
        announce(progress, "building %s environment" % side)
        side_dir = os.path.join(evidence_dir, side)
        env_dir = os.path.join(work_dir, side)
        build = build_environment(
            side, env_dir, lines, side_dir, python_bin,
            use_cache=use_cache, install_timeout=install_timeout,
        )

        graph = build_graph(build["packages"], direct)
        write_json(os.path.join(side_dir, "graph.json"), graph)

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
            tests = run_test_suite(env_dir, repo_path, side_dir, timeout=test_timeout)

        sides[side] = {
            "build": strip_packages(build),
            "graph": graph,
            "conflicts": conflicts,
            "vulnerabilities": vulnerabilities,
            "licenses": licenses,
            "tests": tests,
        }
        write_json(os.path.join(side_dir, "summary.json"), sides[side])

    announce(progress, "comparing both environments")
    difference = {
        "graph": diff_graphs(sides["before"]["graph"], sides["after"]["graph"]),
        "conflicts": diff_conflicts(sides["before"]["conflicts"], sides["after"]["conflicts"]),
        "vulnerabilities": diff_vulnerabilities(sides["before"]["vulnerabilities"], sides["after"]["vulnerabilities"]),
        "licenses": diff_licenses(sides["before"]["licenses"], sides["after"]["licenses"]),
        "tests": diff_test_runs(sides["before"]["tests"], sides["after"]["tests"]),
    }

    bundle = {
        "run_id": spec.run_id,
        "spec": spec.to_dict(),
        "policy": policy.to_dict(),
        "python_bin": python_bin,
        "package_was_declared": before_found and after_found,
        "before": sides["before"],
        "after": sides["after"],
        "diff": difference,
        "evidence_dir": evidence_dir,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started)),
    }
    bundle["verdict"] = decide(bundle)
    bundle["total_seconds"] = round(time.time() - started, 2)

    write_json(os.path.join(evidence_dir, "run.json"), bundle["spec"])
    write_json(os.path.join(evidence_dir, "policy.json"), bundle["policy"])
    write_json(os.path.join(evidence_dir, "diff.json"), difference)
    write_json(os.path.join(evidence_dir, "verdict.json"), bundle["verdict"])
    write_json(os.path.join(evidence_dir, "bundle.json"), bundle)
    write_report(bundle, os.path.join(evidence_dir, "report.html"))
    announce(progress, "done")
    return bundle


def strip_packages(build):
    copied = dict(build)
    copied.pop("packages", None)
    return copied


def announce(progress, message):
    if progress:
        progress(message)
