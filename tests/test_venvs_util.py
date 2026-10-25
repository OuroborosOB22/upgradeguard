import os
import sys

from upgradeguard.util import read_json, run_command, write_json
from upgradeguard.venvs import copy_repository, interpreter_path, resolve_python, tail


def test_copy_skips_git_caches_and_previous_runs(tmp_path):
    source = tmp_path / "project"
    for folder in (".git", "__pycache__", "evidence", "work", ".venv", "src"):
        (source / folder).mkdir(parents=True)
        (source / folder / "f.txt").write_text("x")
    (source / "keep.py").write_text("print(1)")
    copy = copy_repository(str(source), str(tmp_path / "copy"))
    assert sorted(os.listdir(copy)) == ["keep.py", "src"]


def test_copy_replaces_an_existing_destination(tmp_path):
    source = tmp_path / "project"
    source.mkdir()
    (source / "a.py").write_text("1")
    destination = tmp_path / "copy"
    destination.mkdir()
    (destination / "stale.py").write_text("old")
    copy_repository(str(source), str(destination))
    assert sorted(os.listdir(destination)) == ["a.py"]


def test_interpreter_path_prefers_the_unix_layout(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "python").write_text("")
    assert interpreter_path(str(tmp_path)) == str(tmp_path / "bin" / "python")
    assert interpreter_path(str(tmp_path / "nowhere")).endswith(os.path.join("Scripts", "python.exe"))


def test_tail_keeps_the_last_non_blank_lines():
    assert tail("a\n\nb\nc\n", lines=2) == "b\nc"


def test_resolve_python_falls_back_to_something_runnable():
    assert os.path.exists(resolve_python("definitely-not-a-python"))
    assert resolve_python(sys.executable) == sys.executable


def test_run_command_captures_output_and_writes_the_log(tmp_path):
    log = tmp_path / "logs" / "run.log"
    result = run_command([sys.executable, "-c", "print('hello')"], log_path=str(log))
    assert result["returncode"] == 0 and "hello" in result["output"]
    assert "exit code 0" in log.read_text()


def test_run_command_reports_timeouts_and_missing_programs(tmp_path):
    slow = run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=1)
    assert slow["timed_out"] is True and slow["returncode"] == -1
    missing = run_command(["no-such-program-anywhere"])
    assert missing["returncode"] == -1 and "NOT FOUND" in missing["output"]


def test_run_command_merges_the_extra_environment():
    result = run_command([sys.executable, "-c", "import os; print(os.environ['UG_TEST'])"], env={"UG_TEST": "yes"})
    assert result["output"].strip() == "yes"


def test_json_helpers_round_trip_and_create_folders(tmp_path):
    path = tmp_path / "deep" / "file.json"
    write_json(str(path), {"b": 1, "a": [1, 2]})
    assert read_json(str(path)) == {"a": [1, 2], "b": 1}


def test_timeout_output_comes_back_as_text(tmp_path):
    result = run_command([sys.executable, "-u", "-c", "import time; print('partial', flush=True); time.sleep(5)"], timeout=1)
    assert result["timed_out"] is True
    assert isinstance(result["output"], str)
    assert "partial" in result["output"]
    assert "TIMED OUT" in result["output"]
