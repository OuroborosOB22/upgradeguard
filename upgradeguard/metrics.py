import statistics

from .verdict import ACCEPT, INSUFFICIENT, REJECT

SIGNALS = ["test-regression", "dependency-conflict", "vulnerability", "licence-violation", "build-failure", "no-tests"]


def ratio(numerator, denominator):
    return round(numerator / denominator, 3) if denominator else None


def decision_metrics(rows, decision_of):
    positives = [row for row in rows if row["expected"] == REJECT]
    negatives = [row for row in rows if row["expected"] == ACCEPT]
    flagged = [row for row in rows if decision_of(row) == REJECT]
    true_flags = [row for row in flagged if row["expected"] == REJECT]
    false_approvals = [row for row in positives if decision_of(row) == ACCEPT]
    false_rejections = [row for row in negatives if decision_of(row) == REJECT]
    correct = [row for row in rows if decision_of(row) == row["expected"]]
    return {
        "cases": len(rows),
        "accuracy": ratio(len(correct), len(rows)),
        "precision": ratio(len(true_flags), len(flagged)),
        "recall": ratio(len(true_flags), len(positives)),
        "false_approvals": len(false_approvals),
        "false_rejections": len(false_rejections),
        "inconclusive": len([row for row in rows if decision_of(row) == INSUFFICIENT]),
    }


def signal_metrics(rows):
    result = {}
    for signal in SIGNALS:
        expecting = [row for row in rows if row["expected_signal"] == signal]
        detected = [row for row in expecting if row["signal_detected"]]
        result[signal] = {"cases": len(expecting), "detected": len(detected), "detection_rate": ratio(len(detected), len(expecting))}
    return result


def build_metrics(rows):
    measured = [row for row in rows if "before_built" in row]
    baseline_ok = [row for row in measured if row["before_built"]]
    upgrade_expected = [row for row in baseline_ok if row["expected_signal"] != "build-failure"]
    upgrade_ok = [row for row in upgrade_expected if row["after_built"]]
    build_failures = [row for row in baseline_ok if row["expected_signal"] == "build-failure"]
    build_failures_found = [row for row in build_failures if not row["after_built"]]
    return {
        "baseline_build_success": ratio(len(baseline_ok), len(measured)),
        "upgrade_build_success": ratio(len(upgrade_ok), len(upgrade_expected)),
        "build_failure_detection": ratio(len(build_failures_found), len(build_failures)),
    }


def time_metrics(rows):
    seconds = sorted(row["seconds"] for row in rows)
    if not seconds:
        return {"mean_seconds": None, "median_seconds": None, "max_seconds": None, "total_seconds": 0}
    return {
        "mean_seconds": round(statistics.mean(seconds), 2),
        "median_seconds": round(statistics.median(seconds), 2),
        "max_seconds": seconds[-1],
        "total_seconds": round(sum(seconds), 2),
    }


def all_methods(rows, baseline_names):
    methods = {"upgradeguard": decision_metrics(rows, lambda row: row["actual"])}
    for name in baseline_names:
        methods[name] = decision_metrics(rows, lambda row, key=name: row["baselines"][key])
    return methods
