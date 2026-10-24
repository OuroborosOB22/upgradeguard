import json
import os

import pytest

from upgradeguard import schemas, snapshots
from upgradeguard.snapshots import (
    INCONCLUSIVE, PASSING, STARTING_ONLY, add_to_index, comparison_warnings, dependency_changes, eligibility_for,
    latest_passing, read_index, runtime_changes, snapshot_identity, changes_in_tests,
)


def build(ok=True):
    return {"ok": ok}


def run_result(ran=True, returncode=0, failed=0, error=0, timed_out=False):
    return {"ran": ran, "returncode": returncode, "timed_out": timed_out, "counts": {"failed": failed, "error": error}}


def test_a_fully_green_verified_run_is_passing():
    assert eligibility_for(build(), run_result(), verified=True) == PASSING


def test_a_run_with_failures_is_only_a_starting_point():
    assert eligibility_for(build(), run_result(returncode=1, failed=2), verified=True) == STARTING_ONLY
    assert eligibility_for(build(), run_result(returncode=1, error=1), verified=True) == STARTING_ONLY


def test_an_unverified_snapshot_is_never_passing():
    assert eligibility_for(build(), run_result(), verified=False) == STARTING_ONLY


@pytest.mark.parametrize("case", [(build(False), run_result()), (build(), run_result(ran=False)), (build(), run_result(timed_out=True))])
def test_runs_that_could_not_finish_are_inconclusive(case):
    assert eligibility_for(case[0], case[1], verified=True) == INCONCLUSIVE


def test_identity_is_stable_and_sensitive_to_every_input():
    records = [{"id": "a", "outcome": "PASS"}]
    base = snapshot_identity("m" * 64, "pytest-default", records, PASSING)
    assert base == snapshot_identity("m" * 64, "pytest-default", records, PASSING)
    assert base.startswith("snap-") and len(base) == 17
    assert base != snapshot_identity("n" * 64, "pytest-default", records, PASSING)
    assert base != snapshot_identity("m" * 64, "pytest-other", records, PASSING)
    assert base != snapshot_identity("m" * 64, "pytest-default", [{"id": "a", "outcome": "FAIL"}], PASSING)
    assert base != snapshot_identity("m" * 64, "pytest-default", records, STARTING_ONLY)


def snapshot_with(results, dependencies=None, **environment):
    env = {"os": "linux", "architecture": "arm64", "runtimes": {"python": "3.12.4"}}
    env.update(environment)
    return {"tests": {"results": [{"id": name, "outcome": outcome} for name, outcome in results.items()], "ran": True},
            "resolved_dependencies": [{"name": n, "version": v} for n, v in (dependencies or {}).items()],
            "environment": env, "profile_id": "pytest-default", "eligibility": PASSING}


def test_changes_in_tests_separate_failing_skipped_missing_fixed_and_new():
    old = snapshot_with({"a": "PASS", "b": "PASS", "c": "PASS", "d": "FAIL", "e": "PASS"})
    new = snapshot_with({"a": "FAIL", "b": "SKIP", "d": "PASS", "e": "PASS", "f": "PASS"})
    assert changes_in_tests(old, new) == {"newly_failing": ["a"], "newly_skipped": ["b"], "missing": ["c"], "fixed": ["d"], "added": ["f"]}


def test_dependency_changes():
    old = snapshot_with({}, {"a": "1", "b": "1", "c": "1"})
    new = snapshot_with({}, {"a": "2", "c": "1", "d": "1"})
    assert dependency_changes(old, new) == {"added": ["d"], "removed": ["b"], "changed": [{"name": "a", "from": "1", "to": "2"}]}


def test_runtime_changes_and_the_host_warning():
    old = snapshot_with({})
    new = snapshot_with({}, os="darwin")
    new["environment"]["runtimes"] = {"python": "3.13.1"}
    changes = runtime_changes(old, new)
    assert {"field": "os", "from": "linux", "to": "darwin"} in changes
    assert {"field": "runtime python", "from": "3.12.4", "to": "3.13.1"} in changes
    assert any("different hosts" in text for text in comparison_warnings(old, new, changes))


def test_warnings_cover_profile_and_non_passing_baselines():
    old = snapshot_with({})
    new = snapshot_with({})
    new["profile_id"] = "pytest-other"
    old["eligibility"] = STARTING_ONLY
    text = " ".join(comparison_warnings(old, new, []))
    assert "different verification profiles" in text and "not a fully passing run" in text and "lead, not proof" in text


def test_index_keeps_one_entry_per_snapshot_and_finds_the_latest_passing(tmp_path):
    store = str(tmp_path)
    for index, (name, eligibility, profile) in enumerate([("snap-1", PASSING, "p"), ("snap-2", STARTING_ONLY, "p"), ("snap-3", PASSING, "q")]):
        add_to_index(store, "proj", {"snapshot_id": name, "created_at": "2026-10-24T10:0%d:00Z" % index, "eligibility": eligibility,
                                    "profile_id": profile, "manifest_sha256": "x"})
    add_to_index(store, "proj", {"snapshot_id": "snap-1", "created_at": "2026-10-24T10:00:00Z", "eligibility": PASSING, "profile_id": "p", "manifest_sha256": "x"})
    assert len(read_index(store, "proj")) == 3
    assert latest_passing(store, "proj") == "snap-3"
    assert latest_passing(store, "proj", profile="p") == "snap-1"
    assert latest_passing(store, "proj", exclude="snap-3") == "snap-1"
    assert latest_passing(store, "other") is None


def test_loading_a_snapshot_refuses_path_tricks(tmp_path):
    for bad in ("../x", "a/b", "..", ""):
        with pytest.raises(FileNotFoundError):
            snapshots.load_snapshot(str(tmp_path), "proj", bad)


def test_a_missing_requirements_file_is_reported_clearly(tmp_path):
    (tmp_path / "project").mkdir()
    with pytest.raises(FileNotFoundError):
        snapshots.capture_snapshot(str(tmp_path / "project"), str(tmp_path / "store"))
