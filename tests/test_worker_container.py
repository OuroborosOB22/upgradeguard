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


def sample_output(tmp_path):
    from upgradeguard.contract import file_sha256
    directory = tmp_path / "out" / "run-worker-test"
    (directory / "after").mkdir(parents=True)
    (directory / "bundle.json").write_text("{}")
    (directory / "after" / "pytest.log").write_text("log")
    request = make_request(write_project(tmp_path))
    evidence = json.loads(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "contracts", "v1", "fixtures", "valid", "evidence_reject.json")).read())
    evidence["run_id"] = request["run_id"]
    evidence["request"] = request
    evidence["artifact_manifest"] = [
        {"id": "bundle.json", "path": "bundle.json", "sha256": file_sha256(str(directory / "bundle.json")), "media_type": "application/json"},
        {"id": "after-pytest.log", "path": "after/pytest.log", "sha256": file_sha256(str(directory / "after" / "pytest.log")), "media_type": "text/plain"},
    ]
    for item in evidence["verdict"]["findings"]:
        item["evidence_ids"] = ["after-pytest.log"]
    (directory / "evidence.json").write_text(json.dumps(evidence))
    return directory, request


def test_untouched_container_output_is_accepted(tmp_path):
    directory, request = sample_output(tmp_path)
    assert container.verify_output(str(directory), request)["verdict"]["decision"] == "REJECT"


def test_a_symlink_in_the_output_is_refused(tmp_path):
    directory, request = sample_output(tmp_path)
    os.symlink("/etc/passwd", str(directory / "after" / "shortcut"))
    with pytest.raises(container.UntrustedOutput, match="link"):
        container.verify_output(str(directory), request)


def test_a_file_changed_after_its_hash_was_recorded_is_refused(tmp_path):
    directory, request = sample_output(tmp_path)
    (directory / "after" / "pytest.log").write_text("forged")
    with pytest.raises(container.UntrustedOutput, match="hash"):
        container.verify_output(str(directory), request)


def test_extra_and_missing_files_are_refused(tmp_path):
    directory, request = sample_output(tmp_path)
    (directory / "planted.txt").write_text("x")
    with pytest.raises(container.UntrustedOutput, match="manifest"):
        container.verify_output(str(directory), request)
    (directory / "planted.txt").unlink()
    (directory / "bundle.json").unlink()
    with pytest.raises(container.UntrustedOutput, match="manifest"):
        container.verify_output(str(directory), request)


def test_evidence_for_another_job_or_source_is_refused(tmp_path):
    directory, request = sample_output(tmp_path)
    other = dict(request)
    other["run_id"] = "some-other-run"
    with pytest.raises(container.UntrustedOutput, match="belong"):
        container.verify_output(str(directory), other)


def test_evidence_that_breaks_the_schema_is_refused(tmp_path):
    directory, request = sample_output(tmp_path)
    broken = json.loads((directory / "evidence.json").read_text())
    broken["verdict"]["decision"] = "MAYBE"
    (directory / "evidence.json").write_text(json.dumps(broken))
    with pytest.raises(schemas.ContractError):
        container.verify_output(str(directory), request)


def test_oversized_output_is_refused(tmp_path, monkeypatch):
    directory, request = sample_output(tmp_path)
    monkeypatch.setattr(container, "MAX_OUTPUT_BYTES", 1)
    with pytest.raises(container.UntrustedOutput, match="larger"):
        container.verify_output(str(directory), request)


def test_publish_copies_regular_files_only_and_replaces_old_content(tmp_path):
    from upgradeguard.worker import publish
    out = tmp_path / "out"
    (out / "run" / "after").mkdir(parents=True)
    (out / "run" / "after" / "a.log").write_text("log")
    (out / "result.json").write_text("{}")
    os.symlink("/etc/passwd", str(out / "run" / "link"))
    target = tmp_path / "published"
    (target / "stale").mkdir(parents=True)
    (target / "stale" / "old.txt").write_text("old")
    publish(str(out), str(target))
    assert (target / "run" / "after" / "a.log").read_text() == "log"
    assert (target / "result.json").exists()
    assert not (target / "run" / "link").exists() and not (target / "stale").exists()


def test_copy_output_copies_regular_files(tmp_path):
    source = tmp_path / "src"
    (source / "a").mkdir(parents=True)
    (source / "a" / "f.txt").write_text("data")
    container.copy_output(str(source), str(tmp_path / "dst"))
    assert (tmp_path / "dst" / "a" / "f.txt").read_text() == "data"


def test_copy_output_refuses_links_to_files_and_folders(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    os.symlink("/etc/passwd", str(source / "file-link"))
    with pytest.raises(container.UntrustedOutput):
        container.copy_output(str(source), str(tmp_path / "dst"))
    (source / "file-link").unlink()
    os.symlink("/etc", str(source / "folder-link"))
    with pytest.raises(container.UntrustedOutput):
        container.copy_output(str(source), str(tmp_path / "dst2"))


def test_copy_output_refuses_pipes(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    os.mkfifo(str(source / "pipe"))
    with pytest.raises(container.UntrustedOutput, match="regular"):
        container.copy_output(str(source), str(tmp_path / "dst"))


def bundle_for(request, decision="Reject", package="six", from_version="1.16.0", to_version="1.17.0"):
    return {"verdict": {"decision": decision}, "spec": {"package": package, "from_version": from_version, "to_version": to_version}}


def test_bundle_must_agree_with_the_verified_evidence_and_the_request(tmp_path):
    directory, request = sample_output(tmp_path)
    evidence = json.loads((directory / "evidence.json").read_text())
    container.check_bundle_matches(bundle_for(request), evidence, request)
    with pytest.raises(container.UntrustedOutput, match="verdict"):
        container.check_bundle_matches(bundle_for(request, decision="Accept"), evidence, request)
    with pytest.raises(container.UntrustedOutput, match="different change"):
        container.check_bundle_matches(bundle_for(request, to_version="9.9"), evidence, request)
    with pytest.raises(container.UntrustedOutput, match="different change"):
        container.check_bundle_matches(bundle_for(request, package="other"), evidence, request)
