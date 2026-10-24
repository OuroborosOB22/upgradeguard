from upgradeguard.metrics import all_methods, build_metrics, decision_metrics, signal_metrics, time_metrics


def row(expected, actual, signal="none", detected=True, before=True, after=True, seconds=10, **baselines):
    return {"expected": expected, "actual": actual, "expected_signal": signal, "signal_detected": detected,
            "before_built": before, "after_built": after, "seconds": seconds, "baselines": baselines}


ROWS = [
    row("Accept", "Accept"),
    row("Accept", "Reject"),
    row("Reject", "Reject", "test-regression"),
    row("Reject", "Accept", "test-regression", detected=False),
    row("Reject", "Reject", "build-failure", after=False),
    row("Reject", "Insufficient Evidence", "vulnerability", detected=False),
]


def test_decision_metrics_count_each_kind_of_error():
    result = decision_metrics(ROWS, lambda item: item["actual"])
    assert result["cases"] == 6
    assert result["false_approvals"] == 1
    assert result["false_rejections"] == 1
    assert result["inconclusive"] == 1
    assert result["accuracy"] == 0.5
    assert result["precision"] == 0.667
    assert result["recall"] == 0.5


def test_metrics_are_none_not_zero_when_undefined():
    result = decision_metrics([row("Accept", "Accept")], lambda item: item["actual"])
    assert result["precision"] is None and result["recall"] is None


def test_signal_metrics_report_detection_per_signal():
    result = signal_metrics(ROWS)
    assert result["test-regression"] == {"cases": 2, "detected": 1, "detection_rate": 0.5}
    assert result["build-failure"]["detection_rate"] == 1.0
    assert result["licence-violation"]["detection_rate"] is None


def test_build_metrics_separate_expected_and_unexpected_failures():
    result = build_metrics(ROWS)
    assert result["baseline_build_success"] == 1.0
    assert result["upgrade_build_success"] == 1.0
    assert result["build_failure_detection"] == 1.0
    broken = build_metrics([row("Reject", "Reject", before=False)])
    assert broken["baseline_build_success"] == 0.0
    assert broken["upgrade_build_success"] is None


def test_time_metrics():
    result = time_metrics([row("Accept", "Accept", seconds=s) for s in (4, 10, 16)])
    assert result == {"mean_seconds": 10.0, "median_seconds": 10.0, "max_seconds": 16, "total_seconds": 30}
    assert time_metrics([])["mean_seconds"] is None


def test_all_methods_scores_baselines_with_the_same_rules():
    rows = [row("Reject", "Reject", **{"pip-check": "Accept"}), row("Accept", "Accept", **{"pip-check": "Accept"})]
    methods = all_methods(rows, ["pip-check"])
    assert methods["upgradeguard"]["recall"] == 1.0
    assert methods["pip-check"]["false_approvals"] == 1


def test_conflict_cases_do_not_count_against_the_upgraded_build_rate():
    rows = [row("Reject", "Reject", "dependency-conflict", after=False), row("Accept", "Accept", after=True)]
    assert build_metrics(rows)["upgrade_build_success"] == 1.0
