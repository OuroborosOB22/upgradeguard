import os
import time
from concurrent.futures import ThreadPoolExecutor

from .baselines import BASELINE_NAMES, baseline_verdicts
from .metrics import all_methods, build_metrics, signal_metrics, time_metrics
from .report_benchmark import write_results_markdown
from .runner import run_upgrade_check
from .spec import UpgradeSpec, load_policy
from .util import read_json, write_json

SIGNAL_CODES = {
    "test-regression": {"test-regression", "tests-could-not-start"},
    "dependency-conflict": {"new-dependency-conflict", "upgrade-dependency-conflict"},
    "vulnerability": {"new-vulnerability"},
    "licence-violation": {"licence-policy-violation", "licence-policy-precondition"},
    "build-failure": {"upgrade-build-failed", "baseline-build-failed"},
    "no-tests": {"tests-did-not-run"},
    "none": set(),
}


def load_cases(path):
    payload = read_json(path)
    return payload.get("version", "unversioned"), payload.get("cases", [])


def run_case(case, args, base_dir):
    spec = UpgradeSpec(
        repo_path=os.path.join(base_dir, case["repo"]),
        package=case["package"],
        from_version=case["from"],
        to_version=case["to"],
        python_bin=case.get("python", args.python_bin),
        policy_path=case.get("policy", ""),
        requirements_file=case.get("requirements", "requirements.txt"),
        install_project=case.get("install_project", False),
        pytest_args=case.get("pytest_args", []),
        build_env=case.get("env", {}),
        run_id="%s-%s" % (time.strftime("%Y%m%d-%H%M%S"), case["id"]),
        label=case["id"],
    )
    policy_path = os.path.join(base_dir, case["policy"]) if case.get("policy") else ""
    policy = load_policy(policy_path if policy_path and os.path.isfile(policy_path) else "")
    return run_upgrade_check(
        spec,
        policy,
        evidence_root=args.evidence,
        work_root=args.work,
        allow_network=not args.offline,
        test_timeout=args.test_timeout,
        strict_licences=case.get("strict_licences", False),
    )


def observed_codes(bundle):
    return {item["code"] for item in bundle["verdict"]["reasons"]}


def score_case(case, bundle):
    expected_verdict = case["expected"]
    actual_verdict = bundle["verdict"]["decision"]
    expected_signal = case.get("expected_signal", "none")
    wanted = SIGNAL_CODES.get(expected_signal, set())
    codes = observed_codes(bundle)

    signal_found = True if not wanted else bool(wanted & codes)
    return {
        "id": case["id"],
        "repo": case["repo"],
        "package": case["package"],
        "from": case["from"],
        "to": case["to"],
        "expected": expected_verdict,
        "actual": actual_verdict,
        "verdict_correct": expected_verdict == actual_verdict,
        "expected_signal": expected_signal,
        "signal_detected": signal_found,
        "codes": sorted(codes),
        "seconds": bundle["total_seconds"],
        "evidence_dir": bundle["evidence_dir"],
        "regressions": len(bundle["diff"]["tests"]["regressions"]),
        "before_built": bundle["before"]["build"]["ok"],
        "after_built": bundle["after"]["build"]["ok"],
        "baselines": baseline_verdicts(bundle),
    }


def summarise(rows):
    total = len(rows)
    correct = len([row for row in rows if row["verdict_correct"]])
    false_approvals = [row for row in rows if row["expected"] == "Reject" and row["actual"] == "Accept"]
    false_rejections = [row for row in rows if row["expected"] == "Accept" and row["actual"] == "Reject"]
    unsafe_rows = [row for row in rows if row["expected"] == "Reject"]
    detected = [row for row in unsafe_rows if row["signal_detected"]]
    flagged = [row for row in rows if row["actual"] == "Reject"]
    true_flags = [row for row in flagged if row["expected"] == "Reject"]

    precision = len(true_flags) / len(flagged) if flagged else 0.0
    recall = len(true_flags) / len(unsafe_rows) if unsafe_rows else 0.0
    return {
        "cases": total,
        "verdict_accuracy": round(correct / total, 3) if total else 0.0,
        "signal_detection": round(len(detected) / len(unsafe_rows), 3) if unsafe_rows else 0.0,
        "false_approvals": len(false_approvals),
        "false_rejections": len(false_rejections),
        "reject_precision": round(precision, 3),
        "reject_recall": round(recall, 3),
        "mean_seconds": round(sum(row["seconds"] for row in rows) / total, 2) if total else 0.0,
        "total_seconds": round(sum(row["seconds"] for row in rows), 2),
    }


def execute_case(case, args, base_dir):
    try:
        return score_case(case, run_case(case, args, base_dir))
    except Exception as failure:
        return {
            "id": case["id"],
            "repo": case.get("repo", ""),
            "package": case.get("package", ""),
            "from": case.get("from", ""),
            "to": case.get("to", ""),
            "expected": case.get("expected", ""),
            "actual": "Run Error",
            "verdict_correct": False,
            "expected_signal": case.get("expected_signal", "none"),
            "signal_detected": False,
            "codes": [],
            "seconds": 0.0,
            "evidence_dir": "",
            "regressions": 0,
            "error": str(failure),
        }


def scorable(rows):
    return [row for row in rows if "baselines" in row]


def command_benchmark(args):
    base_dir = os.path.dirname(os.path.abspath(args.cases))
    base_dir = os.path.dirname(base_dir) if os.path.basename(base_dir) == "benchmark" else base_dir
    version, cases = load_cases(args.cases)
    if args.only:
        cases = [case for case in cases if case["id"] in set(args.only)]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(execute_case, case, args, base_dir) for case in cases]
        for index, (case, future) in enumerate(zip(cases, futures), start=1):
            rows.append(future.result())
            print("[%d/%d] %s: expected %s, got %s" % (index, len(cases), case["id"], rows[-1]["expected"], rows[-1]["actual"]))

    report = build_report(version, rows, {"jobs": str(args.jobs), "test_timeout": str(args.test_timeout)})
    write_json(args.output, report)
    write_results_markdown(report, os.path.splitext(args.output)[0] + ".md")
    print_table(report)
    return 0 if report["summary"]["false_approvals"] == 0 else 1


def build_report(version, rows, provenance=None):
    return {
        "benchmark_version": version,
        "provenance": provenance or {},
        "summary": summarise(rows),
        "methods": all_methods(scorable(rows), BASELINE_NAMES),
        "signals": signal_metrics(scorable(rows)),
        "builds": build_metrics(scorable(rows)),
        "timing": time_metrics(scorable(rows)),
        "results": rows,
    }


def command_rescore(args):
    old = read_json(args.input)
    provenance = dict(old.get("provenance", {}))
    for item in args.note or []:
        key, _, value = item.partition("=")
        provenance[key] = value
    report = build_report(old["benchmark_version"], old["results"], provenance)
    write_json(args.output, report)
    write_results_markdown(report, os.path.splitext(args.output)[0] + ".md")
    print_table(report)
    return 0


def print_table(report):
    print("")
    print("%-28s %-10s %-10s %-6s %s" % ("case", "expected", "actual", "ok", "seconds"))
    print("-" * 70)
    for row in report["results"]:
        print("%-28s %-10s %-10s %-6s %s" % (
            row["id"][:28], row["expected"], row["actual"],
            "yes" if row["verdict_correct"] else "NO", row["seconds"]))
    print("")
    for key, value in report["summary"].items():
        print("%-20s %s" % (key, value))
