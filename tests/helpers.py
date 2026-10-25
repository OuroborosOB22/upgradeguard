import copy

EMPTY_TESTS = {"ran": True, "results": {}, "counts": {}}


def side(build_ok=True, tests_ran=True, stage=""):
    return {
        "build": {"ok": build_ok, "failure_stage": stage},
        "tests": {"ran": tests_ran, "results": {}, "counts": {}, "timed_out": False, "startup_error": False},
        "licenses": {"violations": [], "unknown": []},
    }


def empty_diff():
    return {
        "conflicts": {"introduced": [], "resolved": []},
        "vulnerabilities": {"introduced": [], "resolved": []},
        "licenses": {"introduced": [], "resolved": [], "new_unknown": []},
        "tests": {"regressions": [], "new_failing_tests": []},
    }


def make_bundle(**changes):
    bundle = {
        "spec": {"package": "requests", "from_version": "2.28.2", "to_version": "2.32.5"},
        "before": side(),
        "after": side(),
        "diff": empty_diff(),
        "options": {"strict_licences": False},
    }
    for key, value in changes.items():
        bundle[key] = copy.deepcopy(value)
    return bundle


def reason_codes(verdict):
    return [item["code"] for item in verdict["reasons"]]


def note_codes(verdict):
    return [item["code"] for item in verdict["notes"]]
