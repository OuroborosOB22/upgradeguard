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


def fake_environment(tmp_path):
    import os
    import stat
    import sys
    scripts = tmp_path / "env" / "bin"
    scripts.mkdir(parents=True)
    wrapper = scripts / "python"
    wrapper.write_text("#!/bin/sh\nexec %s \"$@\"\n" % sys.executable)
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    return str(tmp_path / "env")


def write_project(tmp_path, body):
    project = tmp_path / "project"
    project.mkdir()
    (project / "test_sample.py").write_text(body)
    return str(project)


def test_run_test_suite_collects_results(tmp_path):
    from upgradeguard.tests_run import run_test_suite
    project = write_project(tmp_path, "def test_a():\n    assert True\n\ndef test_b():\n    assert False\n")
    result = run_test_suite(fake_environment(tmp_path), project, str(tmp_path / "out"))
    assert result["ran"] is True
    assert result["counts"]["passed"] == 1 and result["counts"]["failed"] == 1
    assert (tmp_path / "out" / "junit.xml").exists()


def test_a_run_that_collects_nothing_does_not_count_as_ran(tmp_path):
    from upgradeguard.tests_run import run_test_suite
    project = write_project(tmp_path, "def test_a():\n    assert True\n")
    result = run_test_suite(fake_environment(tmp_path), project, str(tmp_path / "out"), extra_args=["-k", "nomatch"])
    assert result["ran"] is False
    assert result["junit_path"] == ""


def test_a_broken_test_module_does_not_hide_the_good_ones(tmp_path):
    from upgradeguard.tests_run import run_test_suite
    project = write_project(tmp_path, "def test_a():\n    assert True\n")
    (tmp_path / "project" / "test_broken.py").write_text("import module_that_does_not_exist\n")
    result = run_test_suite(fake_environment(tmp_path), project, str(tmp_path / "out"))
    assert result["ran"] is True
    assert result["counts"]["passed"] == 1
    assert result["counts"]["error"] == 1


def test_paths_of_the_two_copies_are_made_comparable(tmp_path):
    path = tmp_path / "junit.xml"
    path.write_text('<testsuites><testcase classname="t" name="test_x[/work/before/repo/tests/a.py]" file="tests/a.py"/></testsuites>')
    before = parse_junit(str(path), {"/work/before/repo": "<repo>"})
    assert list(before) == ["tests/a.py::test_x[<repo>/tests/a.py]"]


def test_longer_prefixes_are_replaced_first(tmp_path):
    from upgradeguard.tests_run import stable_identifier
    aliases = {"/work/env": "<env>", "/work/env/lib": "<lib>"}
    assert stable_identifier("x[/work/env/lib/a]", aliases) == "x[<lib>/a]"


def test_a_passing_test_that_becomes_skipped_is_a_regression():
    diff = diff_test_runs(results(a="passed"), results(a="skipped"))
    assert [(item["test"], item["after"]) for item in diff["regressions"]] == [("a", "skipped")]


def test_a_test_that_was_already_skipped_is_not_a_regression():
    assert diff_test_runs(results(a="skipped"), results(a="skipped"))["regressions"] == []


def test_tool_driven_test_runs_are_marked_so_the_recorder_stays_quiet(tmp_path):
    from upgradeguard.tests_run import environment_for, run_test_suite
    project = write_project(tmp_path, "import os\n\ndef test_marker():\n    assert os.environ['UPGRADEGUARD_ACTIVE'] == '1'\n")
    environment = fake_environment(tmp_path)
    assert environment_for(environment)["UPGRADEGUARD_ACTIVE"] == "1"
    result = run_test_suite(environment, project, str(tmp_path / "out"))
    assert result["counts"]["passed"] == 1
