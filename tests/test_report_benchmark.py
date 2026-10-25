from upgradeguard.report_benchmark import percent, render_results


def report():
    method = {"accuracy": 0.5, "precision": None, "recall": 1.0, "false_approvals": 1, "false_rejections": 0, "inconclusive": 0}
    return {
        "summary": {"cases": 2},
        "methods": {"upgradeguard": method, "pip-check": method},
        "signals": {"test-regression": {"cases": 1, "detected": 1, "detection_rate": 1.0}},
        "builds": {"baseline_build_success": 1.0, "upgrade_build_success": None, "build_failure_detection": 0.5},
        "timing": {"mean_seconds": 5, "median_seconds": 5, "max_seconds": 6, "total_seconds": 10},
        "results": [{"id": "case-1", "expected": "Accept", "actual": "Reject", "verdict_correct": False, "seconds": 5.5}],
    }


def test_percent_handles_undefined_values():
    assert percent(None) == "n/a"
    assert percent(0.6667) == "66.7%"


def test_markdown_contains_every_section_and_the_failing_case():
    text = render_results(report())
    for heading in ("## Verdicts against the baselines", "## Detection by signal", "## Environment builds", "## Every case"):
        assert heading in text
    assert "| UpgradeGuard | 50.0% | n/a | 100.0% | 1 | 0 | 0 |" in text
    assert "| pip check only |" in text
    assert "| case-1 | Accept | Reject | NO | 5.5 |" in text
    assert "baseline environment built: 100.0%" in text
