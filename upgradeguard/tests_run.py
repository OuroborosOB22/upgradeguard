import os
import xml.etree.ElementTree as ElementTree

from .venvs import interpreter_path
from .util import run_command

# runs pytest in the sandbox + parses the machine-readable junit XML output + diffs the test results to detect test regressions

STATUS_RANK = {"passed": 0, "skipped": 1, "failed": 2, "error": 2}
STARTUP_MARKERS = ("ImportError", "ModuleNotFoundError", "ConftestImportFailure")


def run_test_suite(env_dir, repo_path, output_dir, timeout=900, extra_args=None):
    junit_path = os.path.join(output_dir, "junit.xml")
    log_path = os.path.join(output_dir, "pytest.log")
    result = run_command(
        [
            interpreter_path(env_dir), "-m", "pytest",
            "--junitxml", junit_path,
            "-q", "-p", "no:cacheprovider",
            "--continue-on-collection-errors", # -flag forces pytest to continue running the rest of the test suite
            # if one test file has a broken import pytest aborts tests and skips all other test files
            "--rootdir", repo_path,
        ] + list(extra_args or []),
        cwd=repo_path,
        log_path=log_path,
        timeout=timeout,
        env=environment_for(env_dir),
    )

    parsed = parse_junit(junit_path, {repo_path: "<repo>", env_dir: "<env>"})
    collected = bool(parsed)
    return {
        "ran": collected,
        "startup_error": not collected and result["returncode"] in (2, 3, 4) and any(mark in result["output"] for mark in STARTUP_MARKERS),
        "returncode": result["returncode"],
        "timed_out": result["timed_out"],
        "duration": result["duration"],
        "junit_path": junit_path if collected else "",
        "log_path": log_path,
        "results": parsed or {},
        "counts": count_statuses(parsed or {}),
        "tail": tail_lines(result["output"]),
    }


def environment_for(env_dir):
    scripts = os.path.dirname(interpreter_path(env_dir))
    return {"VIRTUAL_ENV": env_dir, "PATH": scripts + os.pathsep + os.environ.get("PATH", ""), "UPGRADEGUARD_ACTIVE": "1"}


def parse_junit(path, path_aliases=None): # usual junit tagging recog
    if not os.path.isfile(path):
        return None
    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError:
        return None

    results = {}
    for case in tree.getroot().iter("testcase"):
        identifier = stable_identifier(build_identifier(case), path_aliases or {})
        status = "passed"
        message = ""
        for child in case:
            tag = child.tag
            if tag == "failure":
                status = "failed"
            elif tag == "error":
                status = "error"
            elif tag == "skipped":
                status = "skipped"
            else:
                continue
            message = (child.get("message") or "").strip().split("\n")[0][:300]
            break
        previous = results.get(identifier)
        if previous is None or STATUS_RANK[status] > STATUS_RANK[previous["status"]]:
            results[identifier] = {"status": status, "message": message, "time": case.get("time", "0")}
    return results


def stable_identifier(identifier, path_aliases):
    for prefix, alias in sorted(path_aliases.items(), key=lambda item: -len(item[0])):
        if prefix:
            identifier = identifier.replace(prefix, alias)
    return identifier


def build_identifier(case):
    file_name = case.get("file") or ""
    class_name = case.get("classname") or ""
    name = case.get("name") or ""
    if file_name:
        return "%s::%s" % (file_name, name)
    return "%s::%s" % (class_name, name)


def count_statuses(results):
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "total": 0}
    for entry in results.values():
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
        counts["total"] += 1
    return counts


def tail_lines(text, limit=30):
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])

# RDA(regression detection algo)
# test is a regression if it passed in the before environment but failed or error in the after environment
# if a test was already failing before the upgrade (previous["status"] in broken), it is not a regression & upgrade did not break it
# if a test passed before but is missing after results (because the test file failed to import or was deleted) it is counted as a regression ("not collected")
# if a test failed before and passes after then it is recorded under fixed

def diff_test_runs(before, after):
    before_results = before.get("results", {})
    after_results = after.get("results", {})
    broken = {"failed", "error"} # or "skipped"

    regressions = []
    fixed = []
    new_tests = []
    removed_tests = []

    for identifier in sorted(after_results):
        current = after_results[identifier]
        if identifier not in before_results:
            new_tests.append({
                "test": identifier,
                "status": current["status"],
                "message": current["message"],
            })
            continue
        previous = before_results[identifier]
        if previous["status"] == "passed" and (current["status"] in broken or current["status"] == "skipped"):
            regressions.append({
                "test": identifier,
                "before": previous["status"],
                "after": current["status"],
                "message": current["message"],
            })
        elif previous["status"] in broken and current["status"] == "passed":
            fixed.append({"test": identifier, "before": previous["status"], "after": "passed"})

    for identifier in sorted(before_results):
        if identifier in after_results:
            continue
        previous = before_results[identifier]
        removed_tests.append({"test": identifier, "status": previous["status"]})
        if previous["status"] == "passed":
            regressions.append({
                "test": identifier,
                "before": "passed",
                "after": "not collected",
                "message": "this test passed before the upgrade and could not be collected after it",
            })

    regressions.sort(key=lambda item: item["test"])
    return {
        "regressions": regressions,
        "fixed": fixed,
        "new_tests": new_tests,
        "removed_tests": removed_tests,
        "new_failing_tests": [item for item in new_tests if item["status"] in broken],
        "before_counts": before.get("counts", {}),
        "after_counts": after.get("counts", {}),
    }
