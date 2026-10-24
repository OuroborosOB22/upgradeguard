import json
import os

import pytest

from upgradeguard import container, schemas
from upgradeguard.contract import request_from_parts
from upgradeguard.source import describe_source
from upgradeguard.worker import run_worker


def write_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "requirements.txt").write_text("six==1.16.0\n")
    (project / "test_x.py").write_text("def test_ok():\n    assert True\n")
    return project


def make_request(project, operation="REHEARSE_UPGRADE", to_version="1.17.0", **changes):
    spec = {"package": "six", "from_version": "1.16.0", "to_version": to_version, "pytest_args": [], "build_env": {}}
    request = request_from_parts("run-worker-test", str(project), describe_source(str(project)), spec, "default", "3.12.4", True, operation)
    request.update(changes)
    return request


def write_request(tmp_path, request):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(request))
    return str(path)


def read_result(out):
    result = json.loads((out / "result.json").read_text())
    assert schemas.problems("worker_result", result) == []
    return result


def test_an_invalid_request_gives_a_failed_result_not_a_crash(tmp_path):
    project = write_project(tmp_path)
    bad = make_request(project)
    bad["change"]["to_version"] = "1.0; rm -rf /"
    out = tmp_path / "out"
    result = run_worker(write_request(tmp_path, bad), str(project), str(out), work_dir=str(tmp_path / "work"))
    assert result["job_state"] == "FAILED" and result["verdict"] is None and result["evidence_path"] is None
    assert "not valid contract v1" in result["error"]
    assert read_result(out)["job_state"] == "FAILED"


def test_a_request_for_different_source_bytes_is_refused(tmp_path):
    project = write_project(tmp_path)
    request = make_request(project)
    (project / "test_x.py").write_text("def test_ok():\n    assert False\n")
    result = run_worker(write_request(tmp_path, request), str(project), str(tmp_path / "out"), work_dir=str(tmp_path / "work"))
    assert result["job_state"] == "FAILED"
    assert "does not match" in result["error"]
    assert not (tmp_path / "work").exists() or not os.listdir(tmp_path / "work")


def test_compare_is_not_a_worker_operation(tmp_path):
    project = write_project(tmp_path)
    result = run_worker(write_request(tmp_path, make_request(project, operation="COMPARE")), str(project), str(tmp_path / "out"),
                        work_dir=str(tmp_path / "work"))
    assert result["job_state"] == "FAILED" and "compare command" in result["error"]


def test_a_missing_request_file_is_a_failed_result(tmp_path):
    result = run_worker(str(tmp_path / "nothing.json"), str(tmp_path), str(tmp_path / "out"), work_dir=str(tmp_path / "work"))
    assert result["job_state"] == "FAILED"
    assert result["run_id"] is None


def docker_args(**changes):
    values = dict(image="upgradeguard-runner:local", repo_path="/repo", request_dir="/req", out_dir="/out", digest="sha256:" + "a" * 64, user="501:20")
    values.update(changes)
    return container.docker_command(**values)


def test_container_command_drops_privileges_and_limits_resources():
    command = docker_args()
    joined = " ".join(command)
    assert "--cap-drop ALL" in joined and "no-new-privileges" in joined and "--read-only" in command
    assert "--memory" in command and "--cpus" in command and "--pids-limit" in command
    assert "--privileged" not in command and "--network host" not in joined
    assert "--user 501:20" in joined


def test_container_command_never_mounts_the_docker_socket_or_home():
    command = docker_args()
    mounts = [command[index + 1] for index, value in enumerate(command) if value == "-v"]
    assert not any("docker.sock" in mount or mount.startswith(("/Users", "/home", "/var/run", "/etc")) for mount in mounts)
    assert "docker.sock" not in " ".join(command)
    assert "HOME=/work/home" in command


def test_container_mounts_the_project_read_only():
    command = docker_args()
    mounts = [command[index + 1] for index, value in enumerate(command) if value == "-v"]
    assert "/repo:/input/repo:ro" in mounts and "/req:/input/request:ro" in mounts and "/out:/output:rw" in mounts
    assert len(mounts) == 3


def test_container_does_not_inherit_host_environment_variables():
    command = docker_args()
    environment = [command[index + 1] for index, value in enumerate(command) if value == "-e"]
    assert sorted(item.split("=")[0] for item in environment) == ["HOME", "UPGRADEGUARD_IMAGE_DIGEST"]
    assert "--env-file" not in command


def test_container_extra_arguments_and_offline_flag_come_last():
    command = docker_args(offline=True, extra=["--requirements", "req.txt"])
    assert command[-2:] == ["--requirements", "req.txt"] and "--offline" in command


def test_only_plain_interpreter_names_are_allowed_in_a_container(tmp_path):
    from upgradeguard.spec import UpgradeSpec, load_policy
    spec = UpgradeSpec(repo_path=str(tmp_path), package="six", from_version="1", to_version="2", python_bin="/bin/sh")
    with pytest.raises(ValueError):
        container.run_in_container(spec, load_policy(""), str(tmp_path))
