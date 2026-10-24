import json
import os
import sys

from . import remote, schemas
from .container import DEFAULT_IMAGE, run_in_container
from .contract import utc_now
from .runner import run_upgrade_check
from .snapshots import capture_snapshot, compare_snapshots, latest_passing, load_snapshot, PASSING
from .spec import UpgradeSpec, load_policy, new_run_id
from .util import read_json
from .verdict import ACCEPT, INSUFFICIENT, REJECT
from .worker import result_record, run_worker

EXIT_CODES = {ACCEPT: 0, REJECT: 1, INSUFFICIENT: 2}
FAILURE_EXIT = 3


def progress_line(message):
    sys.stderr.write("  %s\n" % message)
    sys.stderr.flush()


def emit_json(payload):
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    sys.stdout.flush()


def emit_failure(started, failure):
    emit_json(result_record(started, error=str(failure)))
    return FAILURE_EXIT


def spec_from_args(args, from_version, to_version, package):
    return UpgradeSpec(
        repo_path=args.repo, package=package, from_version=from_version, to_version=to_version, python_bin=args.python_bin,
        policy_path=args.policy, requirements_file=args.requirements, label=args.label,
        install_project=args.install_project, pytest_args=args.pytest_args)


def execute_run(spec, args, operation):
    policy = load_policy(args.policy if os.path.isfile(args.policy) else "")
    reporter = None if args.quiet else progress_line
    spec.run_id = spec.run_id or new_run_id(spec)
    if args.runner == "remote":
        profiles = remote.load_profiles(args.profiles)
        if args.server not in profiles:
            raise ValueError("--server must name a server in the profiles file (%s)" % (", ".join(sorted(profiles)) or "none found"))
        bundle, _ = remote.run_remote(spec, policy, profiles[args.server], args.evidence, progress=reporter, options={"strict_licences": args.strict_licences})
        return bundle
    if args.runner == "container":
        bundle, _ = run_in_container(spec, policy, args.evidence, image=args.image, offline=args.offline, operation=operation,
                                     progress=reporter, strict_licences=args.strict_licences)
        return bundle
    return run_upgrade_check(
        spec, policy, evidence_root=args.evidence, work_root=args.work, allow_network=not args.offline, use_cache=not args.no_cache,
        test_timeout=args.test_timeout, strict_licences=args.strict_licences, progress=reporter, operation=operation)


def finish_run(bundle, args, print_summary):
    if args.json:
        evidence = read_json(os.path.join(bundle["evidence_dir"], "evidence.json"))
        emit_json(schemas.require_valid("evidence", evidence))
    else:
        print_summary(bundle)
    return EXIT_CODES.get(bundle["verdict"]["decision"], 2)


def run_command(args, print_summary, operation="REHEARSE_UPGRADE"):
    started = utc_now()
    try:
        spec = spec_from_args(args, args.from_version, args.to_version, args.package)
        return finish_run(execute_run(spec, args, operation), args, print_summary)
    except Exception as failure:
        if not args.json:
            raise
        return emit_failure(started, failure)


def command_snapshot_run(args):
    started = utc_now()
    try:
        record, duplicate = capture_snapshot(
            args.repo, args.store, python_bin=args.python_bin, requirements_file=args.requirements, pytest_args=args.pytest_args,
            install_project=args.install_project, verify=not args.no_verify, test_timeout=args.test_timeout,
            allow_network=not args.offline, progress=None if args.quiet else progress_line)
        schemas.require_valid("snapshot", record)
    except Exception as failure:
        if not args.json:
            raise
        return emit_failure(started, failure)
    if args.json:
        emit_json(record)
    else:
        print("%s %s%s" % (record["snapshot_id"], record["eligibility"], " (already recorded)" if duplicate else ""))
        print("tests: %d recorded, store: %s" % (len(record["tests"]["results"]), args.store))
    return 0 if record["eligibility"] != "INCONCLUSIVE" else 2


def command_compare(args):
    started = utc_now()
    try:
        old_id = args.old or latest_passing(args.store, args.project)
        if not old_id:
            raise ValueError("there is no passing snapshot to compare against yet")
        new_id = args.new
        if not new_id:
            record, _ = capture_snapshot(args.repo, args.store, python_bin=args.python_bin, requirements_file=args.requirements,
                                         pytest_args=args.pytest_args, install_project=args.install_project, test_timeout=args.test_timeout,
                                         allow_network=not args.offline, progress=None if args.quiet else progress_line)
            new_id = record["snapshot_id"]
        comparison = schemas.require_valid("comparison", compare_snapshots(args.store, args.project, old_id, new_id))
    except Exception as failure:
        if not args.json:
            raise
        return emit_failure(started, failure)
    if args.json:
        emit_json(comparison)
    else:
        print_comparison(comparison)
    return 0


def print_comparison(comparison):
    changes = comparison["changes"]
    print("%s -> %s" % (comparison["old_snapshot_id"], comparison["new_snapshot_id"]))
    print("code        : %d added, %d removed, %d changed" % tuple(len(changes["code"][key]) for key in ("added", "removed", "changed")))
    print("runtime     : %d difference(s)" % len(changes["runtime"]))
    print("dependencies: %d added, %d removed, %d changed" % tuple(len(changes["dependencies"][key]) for key in ("added", "removed", "changed")))
    print("tests       : %d newly failing, %d newly skipped, %d missing, %d fixed" % tuple(
        len(changes["tests"][key]) for key in ("newly_failing", "newly_skipped", "missing", "fixed")))
    for warning in comparison["warnings"]:
        print("note: %s" % warning)


def current_pin(repo, requirements_file, package):
    from .baselines import pinned_version
    return pinned_version(os.path.join(repo, requirements_file), package)


def command_recover(args, print_summary):
    started = utc_now()
    try:
        snapshot = load_snapshot(args.store, args.project, args.snapshot)
        wanted = {item["name"]: item["version"] for item in snapshot["resolved_dependencies"]}
        from .spec import canonical_name
        target = wanted.get(canonical_name(args.package))
        if not target:
            raise ValueError("snapshot %s does not contain %s" % (args.snapshot, args.package))
        current = current_pin(args.repo, args.requirements, args.package)
        if not current:
            raise ValueError("%s is not pinned with == in %s, so there is no current version to move from" % (args.package, args.requirements))
        spec = spec_from_args(args, current, target, args.package)
        return finish_run(execute_run(spec, args, "REHEARSE_RECOVERY"), args, print_summary)
    except Exception as failure:
        if not args.json:
            raise
        return emit_failure(started, failure)


def command_worker(args):
    options = {"requirements": args.requirements, "pytest_args": args.pytest_args, "install_project": args.install_project,
               "strict_licences": args.strict_licences, "policy": args.policy}
    result = run_worker(args.request, args.source, args.out, python_bin=args.python_bin, offline=args.offline, work_dir=args.work,
                        progress=progress_line, options=options, publish_dir=args.publish)
    return 0 if result["job_state"] == "SUCCEEDED" else FAILURE_EXIT


def command_remote(args):
    profiles = remote.load_profiles(args.profiles)
    if args.server not in profiles:
        print("error: --server must name a server in the profiles file (%s)" % (", ".join(sorted(profiles)) or "none found"), file=sys.stderr)
        return FAILURE_EXIT
    try:
        if args.command == "remote-bootstrap":
            caps = remote.bootstrap(profiles[args.server], os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        else:
            caps = remote.test_connection(profiles[args.server])
    except remote.RemoteError as problem:
        print("%s: %s" % (problem.kind, problem), file=sys.stderr)
        return FAILURE_EXIT
    print("server %s: python %s, %d MB free, worker version %s" % (args.server, caps["python"], caps["disk_free_mb"], caps["worker_version"]))
    return 0
