import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_project(tmp_path, body="def test_a():\n    assert True\n\ndef test_b():\n    assert True\n"):
    project = tmp_path / "plug"
    project.mkdir()
    (project / "test_sample.py").write_text(body)
    return project


def run_pytest(project, store, *args, extra_env=None):
    env = dict(os.environ)
    env.pop("UPGRADEGUARD_ACTIVE", None)
    env.pop("UPGRADEGUARD_SNAPSHOT_DIR", None)
    env["PYTHONPATH"] = ROOT
    env.update(extra_env or {})
    if store is not None:
        env["UPGRADEGUARD_SNAPSHOT_DIR"] = str(store)
    return subprocess.run([sys.executable, "-m", "pytest", "-p", "upgradeguard.pytest_plugin", "-q", "-p", "no:cacheprovider", *args],
                          cwd=project, capture_output=True, text=True, env=env)


def snapshots_in(store):
    index = store / "plug" / "index.json"
    return json.loads(index.read_text()) if index.exists() else []


def test_nothing_is_recorded_unless_the_project_turns_it_on(tmp_path):
    project = make_project(tmp_path)
    done = run_pytest(project, None)
    assert done.returncode == 0
    assert not (tmp_path / "store").exists()


def test_an_enabled_run_records_a_passing_snapshot_with_its_tests(tmp_path):
    project = make_project(tmp_path)
    store = tmp_path / "store"
    done = run_pytest(project, store)
    assert done.returncode == 0, done.stdout + done.stderr
    entries = snapshots_in(store)
    assert len(entries) == 1 and entries[0]["eligibility"] == "PASSING"
    record = json.loads((store / "plug" / entries[0]["snapshot_id"] / "snapshot.json").read_text())
    assert [item["id"] for item in record["tests"]["results"]] == ["test_sample.py::test_a", "test_sample.py::test_b"]


def test_the_same_run_observed_twice_is_recorded_once(tmp_path):
    project = make_project(tmp_path)
    store = tmp_path / "store"
    run_pytest(project, store)
    run_pytest(project, store)
    assert len(snapshots_in(store)) == 1


def test_failing_tests_make_a_starting_only_snapshot_and_keep_their_outcome(tmp_path):
    project = make_project(tmp_path, "def test_a():\n    assert False\n")
    store = tmp_path / "store"
    done = run_pytest(project, store)
    assert done.returncode == 1
    assert snapshots_in(store)[0]["eligibility"] == "STARTING_ONLY"


def test_a_selected_subset_is_recorded_as_its_own_scope(tmp_path):
    project = make_project(tmp_path)
    store = tmp_path / "store"
    run_pytest(project, store)
    run_pytest(project, store, "-k", "test_a")
    entries = snapshots_in(store)
    assert len(entries) == 2
    assert len({entry["profile_id"] for entry in entries}) == 2


def test_a_run_driven_by_the_tool_itself_is_never_recorded(tmp_path):
    project = make_project(tmp_path)
    store = tmp_path / "store"
    run_pytest(project, store, extra_env={"UPGRADEGUARD_ACTIVE": "1"})
    assert snapshots_in(store) == []


def test_a_recording_problem_never_changes_the_test_result(tmp_path):
    project = make_project(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.write_text("a file where a folder is needed")
    done = run_pytest(project, blocked)
    assert done.returncode == 0
    assert "2 passed" in done.stdout
