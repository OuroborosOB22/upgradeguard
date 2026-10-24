import json
import subprocess

import pytest

from upgradeguard.repos import REQUIREMENTS_NAME, fetch_repos, repo_slug


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(cwd)})


@pytest.fixture
def source_repo(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    git("init", "-q", "-b", "main", cwd=source)
    (source / "module.py").write_text("x = 1\n")
    git("add", ".", cwd=source)
    git("commit", "-q", "-m", "first", cwd=source)
    git("tag", "v1", cwd=source)
    return source


def write_setup(tmp_path, source, ref="v1"):
    repos = tmp_path / "repos.json"
    repos.write_text(json.dumps({"repositories": [
        {"name": "someone/thing", "url": "file://%s" % source, "ref": ref, "status": "candidate"},
        {"name": "someone/gone", "url": "file://%s" % source, "ref": ref, "status": "dropped"},
    ]}))
    requirements = tmp_path / "requirements"
    requirements.mkdir()
    (requirements / "someone__thing.txt").write_text("pytest==8.2.2\n")
    return repos, requirements


def test_slug_flattens_the_name():
    assert repo_slug("pallets/click") == "pallets__click"


def test_fetch_clones_at_the_ref_and_places_requirements(tmp_path, source_repo):
    repos, requirements = write_setup(tmp_path, source_repo)
    locked = fetch_repos(str(repos), str(tmp_path / "out"), str(requirements))
    destination = tmp_path / "out" / "someone__thing"
    assert (destination / "module.py").exists()
    assert (destination / REQUIREMENTS_NAME).read_text() == "pytest==8.2.2\n"
    assert list(locked) == ["someone/thing"]
    assert len(locked["someone/thing"]["commit"]) == 40


def test_dropped_repositories_are_not_fetched(tmp_path, source_repo):
    repos, requirements = write_setup(tmp_path, source_repo)
    fetch_repos(str(repos), str(tmp_path / "out"), str(requirements))
    assert not (tmp_path / "out" / "someone__gone").exists()


def test_a_missing_ref_fails_loudly(tmp_path, source_repo):
    repos, requirements = write_setup(tmp_path, source_repo, ref="v404")
    with pytest.raises(RuntimeError, match="clone failed"):
        fetch_repos(str(repos), str(tmp_path / "out"), str(requirements))


def test_a_missing_requirements_file_fails_loudly(tmp_path, source_repo):
    repos, requirements = write_setup(tmp_path, source_repo)
    (requirements / "someone__thing.txt").unlink()
    with pytest.raises(FileNotFoundError):
        fetch_repos(str(repos), str(tmp_path / "out"), str(requirements))


def test_only_filter_limits_what_is_cloned(tmp_path, source_repo):
    repos, requirements = write_setup(tmp_path, source_repo)
    locked = fetch_repos(str(repos), str(tmp_path / "out"), str(requirements), only={"nobody/else"})
    assert locked == {}


def test_second_fetch_keeps_the_clone_and_refreshes_requirements(tmp_path, source_repo):
    repos, requirements = write_setup(tmp_path, source_repo)
    out = tmp_path / "out"
    fetch_repos(str(repos), str(out), str(requirements))
    marker = out / "someone__thing" / "marker.txt"
    marker.write_text("kept")
    (requirements / "someone__thing.txt").write_text("pytest==8.3.5\n")
    import json as _json
    (tmp_path / "repos.lock.json").write_text(_json.dumps({"someone/thing": {"ref": "v1", "commit": _commit(out / "someone__thing")}}))
    fetch_repos(str(repos), str(out), str(requirements))
    assert marker.exists()
    assert (out / "someone__thing" / REQUIREMENTS_NAME).read_text() == "pytest==8.3.5\n"


def _commit(path):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True).stdout.strip()
