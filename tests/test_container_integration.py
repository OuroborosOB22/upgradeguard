import json
import os
import subprocess
import sys

import pytest

from upgradeguard import schemas
from upgradeguard.container import DEFAULT_IMAGE, docker_available, image_digest
from upgradeguard.source import build_manifest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "demo_repo")

pytestmark = [pytest.mark.slow, pytest.mark.container]


@pytest.fixture(scope="session")
def runner_image():
    if not docker_available():
        pytest.skip("Docker is not running")
    if not image_digest(DEFAULT_IMAGE):
        built = subprocess.run(["docker", "build", "-q", "-f", "Dockerfile.runner", "-t", DEFAULT_IMAGE, "."], cwd=ROOT, capture_output=True, text=True)
        assert built.returncode == 0, built.stderr[-500:]
    return DEFAULT_IMAGE


def cli(*arguments, env=None):
    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run([sys.executable, "-m", "upgradeguard", *arguments], cwd=ROOT, capture_output=True, text=True, env=merged)


def test_a_container_run_gives_the_same_verdict_with_the_image_recorded(runner_image, tmp_path):
    before = build_manifest(DEMO)["manifest_sha256"]
    done = cli("run", "--repo", DEMO, "--package", "jinja2", "--from", "3.0.3", "--to", "3.1.6", "--runner", "container", "--json",
               "--evidence", str(tmp_path / "e"), "--work", str(tmp_path / "w"))
    assert done.returncode == 1, done.stderr[-800:]
    evidence = json.loads(done.stdout)
    assert schemas.problems("evidence", evidence) == []
    assert evidence["verdict"]["decision"] == "REJECT"
    assert evidence["request"]["environment_spec"]["image_digest"] == image_digest(runner_image)
    assert evidence["request"]["environment_spec"]["os"] == "linux"
    assert len(evidence["diff"]["tests"]["regressions"]) == 5
    assert build_manifest(DEMO)["manifest_sha256"] == before
    assert list((tmp_path / "e").iterdir()) and not any(item.name.startswith(".container") for item in (tmp_path / "e").iterdir())


ISOLATION_TESTS = '''
import os


def test_host_environment_values_are_not_inherited():
    assert "UG_HOST_SECRET" not in os.environ
    assert "SSH_AUTH_SOCK" not in os.environ


def test_the_docker_socket_is_not_available():
    assert not os.path.exists("/var/run/docker.sock")


def test_the_project_folder_cannot_be_changed():
    for folder in ("/input/repo",):
        try:
            open(os.path.join(folder, "planted.txt"), "w").close()
        except OSError:
            continue
        raise AssertionError("the input folder was writable")


def test_the_host_home_is_not_visible():
    assert not os.path.exists("/Users")


def test_the_process_is_not_root():
    assert os.getuid() != 0
'''


def test_the_container_hides_host_secrets_and_protects_the_input(runner_image, tmp_path):
    project = tmp_path / "isolated"
    project.mkdir()
    (project / "requirements.txt").write_text("six==1.16.0\n")
    (project / "test_isolation.py").write_text(ISOLATION_TESTS)
    done = cli("run", "--repo", str(project), "--package", "six", "--from", "1.16.0", "--to", "1.17.0", "--runner", "container", "--json",
               "--evidence", str(tmp_path / "e"), "--work", str(tmp_path / "w"), env={"UG_HOST_SECRET": "hunter2"})
    assert done.returncode == 0, done.stderr[-800:]
    evidence = json.loads(done.stdout)
    outcomes = {item["id"]: item["outcome"] for item in evidence["after"]["tests"]["results"]}
    assert set(outcomes.values()) == {"PASS"} and len(outcomes) == 5, outcomes
    assert not (project / "planted.txt").exists()


def test_a_local_run_with_the_same_tests_shows_what_the_container_prevents(tmp_path):
    project = tmp_path / "isolated"
    project.mkdir()
    (project / "requirements.txt").write_text("six==1.16.0\n")
    (project / "test_isolation.py").write_text(ISOLATION_TESTS)
    done = cli("run", "--repo", str(project), "--package", "six", "--from", "1.16.0", "--to", "1.17.0", "--json",
               "--evidence", str(tmp_path / "e"), "--work", str(tmp_path / "w"), env={"UG_HOST_SECRET": "hunter2"})
    evidence = json.loads(done.stdout)
    outcomes = {item["id"].split("::")[-1]: item["outcome"] for item in evidence["after"]["tests"]["results"]}
    assert outcomes["test_host_environment_values_are_not_inherited"] == "FAIL"
    assert outcomes["test_the_host_home_is_not_visible"] == "FAIL"
