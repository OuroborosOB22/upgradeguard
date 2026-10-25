import argparse
import os
import sys

from .runner import run_upgrade_check
from .spec import UpgradeSpec, load_policy
from .verdict import ACCEPT, INSUFFICIENT, REJECT

EXIT_CODES = {ACCEPT: 0, REJECT: 1, INSUFFICIENT: 2}


def add_project_flags(command):
    command.add_argument("--repo", default=".")
    command.add_argument("--python", dest="python_bin", default="python3")
    command.add_argument("--requirements", default="requirements.txt")
    command.add_argument("--install-project", dest="install_project", action="store_true")
    command.add_argument("--pytest-arg", dest="pytest_args", action="append", default=[])
    command.add_argument("--json", action="store_true")
    command.add_argument("--quiet", action="store_true")


def add_check_flags(command):
    command.add_argument("--repo", required=True)
    command.add_argument("--policy", default="policies/default.json")
    command.add_argument("--python", dest="python_bin", default="python3")
    command.add_argument("--requirements", default="requirements.txt")
    command.add_argument("--evidence", default="evidence")
    command.add_argument("--work", default="work")
    command.add_argument("--label", default="")
    command.add_argument("--offline", action="store_true")
    command.add_argument("--no-cache", dest="no_cache", action="store_true")
    command.add_argument("--test-timeout", type=int, default=900)
    command.add_argument("--strict-licences", dest="strict_licences", action="store_true")
    command.add_argument("--quiet", action="store_true")
    command.add_argument("--install-project", dest="install_project", action="store_true")
    command.add_argument("--pytest-arg", dest="pytest_args", action="append", default=[])
    command.add_argument("--json", action="store_true")
    command.add_argument("--runner", choices=["local", "container", "remote"], default="local")
    command.add_argument("--image", default="upgradeguard-runner:local")
    command.add_argument("--profiles", default=os.environ.get("UPGRADEGUARD_REMOTE_PROFILES", ""))
    command.add_argument("--server", default="")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="upgradeguard",
        description="Check one Python dependency upgrade by building and testing it twice",
    )
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("run", help="check a single proposed upgrade")
    check.add_argument("--repo", required=True)
    check.add_argument("--package", required=True)
    check.add_argument("--from", dest="from_version", required=True)
    check.add_argument("--to", dest="to_version", required=True)
    check.add_argument("--policy", default="policies/default.json")
    check.add_argument("--python", dest="python_bin", default="python3")
    check.add_argument("--requirements", default="requirements.txt")
    check.add_argument("--evidence", default="evidence")
    check.add_argument("--work", default="work")
    check.add_argument("--label", default="")
    check.add_argument("--offline", action="store_true")
    check.add_argument("--no-cache", dest="no_cache", action="store_true")
    check.add_argument("--test-timeout", type=int, default=900)
    check.add_argument("--strict-licences", dest="strict_licences", action="store_true")
    check.add_argument("--quiet", action="store_true")
    check.add_argument("--install-project", dest="install_project", action="store_true")
    check.add_argument("--pytest-arg", dest="pytest_args", action="append", default=[])
    check.add_argument("--json", action="store_true")
    check.add_argument("--runner", choices=["local", "container", "remote"], default="local")
    check.add_argument("--image", default="upgradeguard-runner:local")
    check.add_argument("--profiles", default=os.environ.get("UPGRADEGUARD_REMOTE_PROFILES", ""), help="file with the named servers, used by --runner remote")
    check.add_argument("--server", default="", help="name of the server in the profiles file")

    for name, text in (("remote-check", "test the connection to a named server"), ("remote-bootstrap", "install the worker on a named server")):
        remote_command = sub.add_parser(name, help=text)
        remote_command.add_argument("--profiles", default=os.environ.get("UPGRADEGUARD_REMOTE_PROFILES", ""))
        remote_command.add_argument("--server", required=True)

    suite = sub.add_parser("benchmark", help="run every case in a benchmark file")
    suite.add_argument("--cases", default="benchmark/cases.json")
    suite.add_argument("--evidence", default="evidence")
    suite.add_argument("--work", default="work")
    suite.add_argument("--python", dest="python_bin", default="python3")
    suite.add_argument("--offline", action="store_true")
    suite.add_argument("--output", default="benchmark/results.json")
    suite.add_argument("--jobs", type=int, default=1)
    suite.add_argument("--test-timeout", type=int, default=900)
    suite.add_argument("--only", nargs="*")

    rescore = sub.add_parser("benchmark-rescore", help="recompute the metrics from an existing results file without running anything")
    rescore.add_argument("--input", default="benchmark/results.json")
    rescore.add_argument("--output", default="benchmark/results.json")
    rescore.add_argument("--note", action="append")

    snap = sub.add_parser("snapshot-run", help="run the tests once and record the result as a snapshot")
    add_project_flags(snap)
    snap.add_argument("--store", default="snapshots")
    snap.add_argument("--no-verify", dest="no_verify", action="store_true")
    snap.add_argument("--test-timeout", type=int, default=900)
    snap.add_argument("--offline", action="store_true")

    cmp = sub.add_parser("compare", help="compare two snapshots, or the current state against the last passing one")
    add_project_flags(cmp)
    cmp.add_argument("--store", default="snapshots")
    cmp.add_argument("--project", required=True)
    cmp.add_argument("--old")
    cmp.add_argument("--new")
    cmp.add_argument("--test-timeout", type=int, default=900)
    cmp.add_argument("--offline", action="store_true")

    rec = sub.add_parser("recover", help="try a previous dependency version from a snapshot in separate copies")
    add_check_flags(rec)
    rec.add_argument("--package", required=True)
    rec.add_argument("--snapshot", required=True)
    rec.add_argument("--project", required=True)
    rec.add_argument("--store", default="snapshots")

    work = sub.add_parser("worker", help="run one job described by a contract v1 request file")
    work.add_argument("--request", required=True)
    work.add_argument("--source", required=True)
    work.add_argument("--out", required=True)
    work.add_argument("--work")
    work.add_argument("--publish")
    work.add_argument("--python", dest="python_bin", default="python3")
    work.add_argument("--requirements", default="requirements.txt")
    work.add_argument("--policy", default="")
    work.add_argument("--pytest-arg", dest="pytest_args", action="append", default=[])
    work.add_argument("--install-project", dest="install_project", action="store_true")
    work.add_argument("--strict-licences", dest="strict_licences", action="store_true")
    work.add_argument("--offline", action="store_true")

    fetch = sub.add_parser("fetch-repos", help="clone the benchmark repositories at their pinned versions")
    fetch.add_argument("--repos", default="benchmark/repos.json")
    fetch.add_argument("--dest", default="benchmark/repos")
    fetch.add_argument("--requirements-dir", dest="requirements_dir", default="benchmark/requirements")
    fetch.add_argument("--only", nargs="*")
    fetch.add_argument("--reclone", action="store_true")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return command_run(args)
    if args.command == "benchmark":
        from .benchmark import command_benchmark
        return command_benchmark(args)
    if args.command == "benchmark-rescore":
        from .benchmark import command_rescore
        return command_rescore(args)
    if args.command == "snapshot-run":
        from .commands import command_snapshot_run
        return command_snapshot_run(args)
    if args.command == "compare":
        from .commands import command_compare
        return command_compare(args)
    if args.command == "recover":
        from .commands import command_recover
        return command_recover(args, print_summary)
    if args.command in ("remote-check", "remote-bootstrap"):
        from .commands import command_remote
        return command_remote(args)
    if args.command == "worker":
        from .commands import command_worker
        return command_worker(args)
    if args.command == "fetch-repos":
        from .repos import command_fetch_repos
        return command_fetch_repos(args)
    parser.print_help()
    return 2


def command_run(args):
    from .commands import run_command
    return run_command(args, print_summary)


def progress_line(message):
    sys.stderr.write("  %s\n" % message)
    sys.stderr.flush()


def print_summary(bundle):
    from .banner import headline, print_banner
    verdict = bundle["verdict"]
    diff = bundle["diff"]
    print_banner()
    print("")
    print(headline(verdict["headline"]))
    print("")
    for item in verdict["reasons"]:
        print("  [%s] %s" % (item["code"], item["message"]))
    for item in verdict["notes"]:
        print("  (%s) %s" % (item["code"], item["message"]))
    print("")
    print("dependency changes : %d added, %d removed, %d version changes" % (
        len(diff["graph"]["added"]), len(diff["graph"]["removed"]), len(diff["graph"]["changed"])))
    print("test regressions   : %d" % len(diff["tests"]["regressions"]))
    # print("python interpreter : %s" % bundle["python_bin"])
    print("new conflicts      : %d" % len(diff["conflicts"]["introduced"]))
    print("new vulnerabilities: %d" % len(diff["vulnerabilities"]["introduced"]))
    print("licence violations : %d new" % len(diff["licenses"]["introduced"]))
    print("evidence           : %s" % bundle["evidence_dir"])
    print("report             : %s" % os.path.join(bundle["evidence_dir"], "report.html"))
    print("total time         : %ss" % bundle["total_seconds"])
 

if __name__ == "__main__":
    sys.exit(main())
