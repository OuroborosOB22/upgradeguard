import os
import time

from .runner import run_upgrade_check
from .spec import UpgradeSpec, load_policy
from .util import read_json, write_json

SIGNAL_CODES = {
    "test-regression": {"test-regression"},
    "dependency-conflict": {"new-dependency-conflict"},
    "vulnerability": {"new-vulnerability"},
    "licence-violation": {"licence-policy-violation", "licence-policy-precondition"},
    "build-failure": {"upgrade-build-failed", "baseline-build-failed"},
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
        python_bin=args.python_bin,
        policy_path=case.get("policy", ""),
        requirements_file=case.get("requirements", "requirements.txt"),
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


def command_benchmark(args):
    base_dir = os.path.dirname(os.path.abspath(args.cases))
    base_dir = os.path.dirname(base_dir) if os.path.basename(base_dir) == "benchmark" else base_dir
    version, cases = load_cases(args.cases)
    rows = []
    for index, case in enumerate(cases, start=1):
        print("[%d/%d] %s" % (index, len(cases), case["id"]))
        try:
            bundle = run_case(case, args, base_dir)
            rows.append(score_case(case, bundle))
        except Exception as failure:
            rows.append({
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
            })
        print("      expected %s, got %s" % (rows[-1]["expected"], rows[-1]["actual"]))

    report = {"benchmark_version": version, "summary": summarise(rows), "results": rows}
    write_json(args.output, report)
    print_table(report)
    return 0 if report["summary"]["false_approvals"] == 0 else 1


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
