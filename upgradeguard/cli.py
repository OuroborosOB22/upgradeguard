import argparse
import os
import sys

from .runner import run_upgrade_check
from .spec import UpgradeSpec, load_policy
from .verdict import ACCEPT, INSUFFICIENT, REJECT

EXIT_CODES = {ACCEPT: 0, REJECT: 1, INSUFFICIENT: 2}


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
    check.add_argument("--quiet", action="store_true")

    suite = sub.add_parser("benchmark", help="run every case in a benchmark file")
    suite.add_argument("--cases", default="benchmark/cases.json")
    suite.add_argument("--evidence", default="evidence")
    suite.add_argument("--work", default="work")
    suite.add_argument("--python", dest="python_bin", default="python3")
    suite.add_argument("--offline", action="store_true")
    suite.add_argument("--output", default="benchmark/results.json")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return command_run(args)
    if args.command == "benchmark":
        from .benchmark import command_benchmark
        return command_benchmark(args)
    parser.print_help()
    return 2


def command_run(args):
    spec = UpgradeSpec(
        repo_path=args.repo,
        package=args.package,
        from_version=args.from_version,
        to_version=args.to_version,
        python_bin=args.python_bin,
        policy_path=args.policy,
        requirements_file=args.requirements,
        label=args.label,
    )
    policy = load_policy(args.policy if os.path.isfile(args.policy) else "")
    reporter = None if args.quiet else progress_line

    bundle = run_upgrade_check(
        spec,
        policy,
        evidence_root=args.evidence,
        work_root=args.work,
        allow_network=not args.offline,
        use_cache=not args.no_cache,
        test_timeout=args.test_timeout,
        progress=reporter,
    )
    print_summary(bundle)
    return EXIT_CODES.get(bundle["verdict"]["decision"], 2)


def progress_line(message):
    sys.stderr.write("  %s\n" % message)
    sys.stderr.flush()


def print_summary(bundle):
    verdict = bundle["verdict"]
    diff = bundle["diff"]
    print("")
    print(verdict["headline"])
    print("-" * len(verdict["headline"]))
    for item in verdict["reasons"]:
        print("  [%s] %s" % (item["code"], item["message"]))
    for item in verdict["notes"]:
        print("  (%s) %s" % (item["code"], item["message"]))
    print("")
    print("dependency changes : %d added, %d removed, %d version changes" % (
        len(diff["graph"]["added"]), len(diff["graph"]["removed"]), len(diff["graph"]["changed"])))
    print("test regressions   : %d" % len(diff["tests"]["regressions"]))
    print("new conflicts      : %d" % len(diff["conflicts"]["introduced"]))
    print("new vulnerabilities: %d" % len(diff["vulnerabilities"]["introduced"]))
    print("licence violations : %d new" % len(diff["licenses"]["introduced"]))
    print("evidence           : %s" % bundle["evidence_dir"])
    print("report             : %s" % os.path.join(bundle["evidence_dir"], "report.html"))
    print("total time         : %ss" % bundle["total_seconds"])


if __name__ == "__main__":
    sys.exit(main())
