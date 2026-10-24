from upgradeguard.tests_run import count_statuses, diff_test_runs, parse_junit

JUNIT = """<?xml version="1.0"?>
<testsuites><testsuite>
  <testcase classname="tests.test_a" name="test_ok" file="tests/test_a.py" time="0.01"/>
  <testcase classname="tests.test_a" name="test_bad" file="tests/test_a.py" time="0.01"><failure message="boom&#10;second line"/></testcase>
  <testcase classname="tests.test_a" name="test_err" file="tests/test_a.py"><error message="import"/></testcase>
  <testcase classname="tests.test_a" name="test_skip" file="tests/test_a.py"><skipped message="why"/></testcase>
  <testcase classname="pkg.mod" name="test_no_file"/>
</testsuite></testsuites>"""


def results(**statuses):
    return {"results": {name: {"status": status, "message": ""} for name, status in statuses.items()}}


def test_parse_junit_reads_every_status(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text(JUNIT)
    parsed = parse_junit(str(path))
    assert parsed["tests/test_a.py::test_ok"]["status"] == "passed"
    assert parsed["tests/test_a.py::test_bad"]["status"] == "failed"
    assert parsed["tests/test_a.py::test_bad"]["message"] == "boom"
    assert parsed["tests/test_a.py::test_err"]["status"] == "error"
    assert parsed["tests/test_a.py::test_skip"]["status"] == "skipped"
    assert "pkg.mod::test_no_file" in parsed


def test_parse_junit_returns_none_for_missing_file(tmp_path):
    assert parse_junit(str(tmp_path / "nothing.xml")) is None


def test_parse_junit_returns_none_for_malformed_xml(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text("<testsuites><testcase")
    assert parse_junit(str(path)) is None


def test_count_statuses_totals_everything():
    counts = count_statuses(results(a="passed", b="failed", c="skipped", d="passed")["results"])
    assert counts["passed"] == 2 and counts["failed"] == 1 and counts["skipped"] == 1 and counts["total"] == 4


def test_pass_to_fail_is_a_regression():
    diff = diff_test_runs(results(a="passed"), results(a="failed"))
    assert [item["test"] for item in diff["regressions"]] == ["a"]


def test_pass_to_error_is_a_regression():
    diff = diff_test_runs(results(a="passed"), results(a="error"))
    assert len(diff["regressions"]) == 1


def test_already_failing_test_is_not_a_regression():
    diff = diff_test_runs(results(a="failed"), results(a="failed"))
    assert diff["regressions"] == []


def test_fixed_test_is_reported_as_fixed():
    diff = diff_test_runs(results(a="failed"), results(a="passed"))
    assert diff["regressions"] == [] and len(diff["fixed"]) == 1


def test_test_that_vanished_counts_as_a_regression():
    diff = diff_test_runs(results(a="passed", b="passed"), results(b="passed"))
    assert [item["test"] for item in diff["regressions"]] == ["a"]
    assert diff["regressions"][0]["after"] == "not collected"


def test_failing_test_that_vanished_is_removed_but_not_a_regression():
    diff = diff_test_runs(results(a="failed"), results())
    assert diff["regressions"] == [] and len(diff["removed_tests"]) == 1


def test_new_failing_test_is_listed_separately():
    diff = diff_test_runs(results(a="passed"), results(a="passed", b="failed", c="passed"))
    assert [item["test"] for item in diff["new_failing_tests"]] == ["b"]
    assert len(diff["new_tests"]) == 2


def test_regressions_come_back_sorted():
    diff = diff_test_runs(results(b="passed", a="passed"), results(b="failed", a="failed"))
    assert [item["test"] for item in diff["regressions"]] == ["a", "b"]
