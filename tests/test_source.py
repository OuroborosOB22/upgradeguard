import io
import os
import subprocess
import tarfile

import pytest

from upgradeguard import source


def make_project(tmp_path):
    root = tmp_path / "project"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("print('a')\n")
    (root / "b.txt").write_text("b\n")
    return root


def test_manifest_lists_files_with_hashes(tmp_path):
    root = make_project(tmp_path)
    manifest = source.build_manifest(str(root))
    assert sorted(manifest["files"]) == ["b.txt", os.path.join("pkg", "a.py")]
    assert len(manifest["manifest_sha256"]) == 64


def test_manifest_is_stable_and_follows_content(tmp_path):
    root = make_project(tmp_path)
    first = source.build_manifest(str(root))["manifest_sha256"]
    assert source.build_manifest(str(root))["manifest_sha256"] == first
    (root / "b.txt").write_text("changed\n")
    assert source.build_manifest(str(root))["manifest_sha256"] != first


def test_secrets_caches_and_history_are_never_selected(tmp_path):
    root = make_project(tmp_path)
    for name in (".env", ".env.production", "server.pem", "id_rsa", "credentials.json", ".netrc", "mod.pyc"):
        (root / name).write_text("secret")
    for folder in (".git", ".venv", "__pycache__", "node_modules", "evidence", "work"):
        (root / folder).mkdir()
        (root / folder / "x.txt").write_text("x")
    files, _ = source.selected_files(str(root))
    assert sorted(files) == ["b.txt", os.path.join("pkg", "a.py")]


def test_symlinks_are_skipped_and_reported(tmp_path):
    root = make_project(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("do not read")
    os.symlink(str(outside), str(root / "link.txt"))
    manifest = source.build_manifest(str(root))
    assert "link.txt" not in manifest["files"]
    assert ("link.txt", "symlink") in manifest["skipped"]


def test_oversized_files_are_skipped(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    monkeypatch.setattr(source, "MAX_FILE_BYTES", 3)
    manifest = source.build_manifest(str(root))
    assert manifest["files"] == {} or all(info["bytes"] <= 3 for info in manifest["files"].values())
    assert any("larger than" in reason for _, reason in manifest["skipped"])


def test_a_project_over_the_total_limit_is_refused(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    monkeypatch.setattr(source, "MAX_TOTAL_BYTES", 4)
    with pytest.raises(source.SourceTooLarge):
        source.build_manifest(str(root))


def test_a_file_that_changes_while_being_read_is_reported(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    original = source.file_digest

    def racing(path):
        digest = original(path)
        if path.endswith("b.txt"):
            with open(path, "a") as handle:
                handle.write("more\n")
        return digest

    monkeypatch.setattr(source, "file_digest", racing)
    manifest = source.build_manifest(str(root))
    assert "b.txt" not in manifest["files"]
    assert ("b.txt", "changed while it was being read") in manifest["skipped"]


def test_git_state_reports_commit_and_dirty_flag(tmp_path):
    root = make_project(tmp_path)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": os.environ["PATH"], "HOME": str(tmp_path)}
    for args in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "x"]):
        subprocess.run(["git", *args], cwd=root, check=True, env=env, capture_output=True)
    commit, dirty = source.git_state(str(root))
    assert len(commit) == 40 and dirty is False
    (root / "b.txt").write_text("edited\n")
    assert source.git_state(str(root))[1] is True


def test_a_folder_that_is_not_a_repository_has_no_commit(tmp_path):
    assert source.git_state(str(make_project(tmp_path))) == (None, False)


def test_describe_source_matches_the_contract_shape(tmp_path):
    described = source.describe_source(str(make_project(tmp_path)))
    assert described["snapshot_id"] == "snap-" + described["manifest_sha256"][:12]
    assert described["commit"] is None and described["dirty"] is False
    assert ".env" in described["exclusions"]


def test_archive_round_trips_and_only_holds_selected_files(tmp_path):
    root = make_project(tmp_path)
    (root / ".env").write_text("secret")
    manifest = source.build_manifest(str(root))
    archive = source.write_archive(str(root), manifest, str(tmp_path / "out" / "src.tar.gz"))
    destination = tmp_path / "restore"
    source.safe_extract(archive, str(destination))
    assert (destination / "b.txt").read_text() == "b\n"
    assert not (destination / ".env").exists()
    assert source.build_manifest(str(destination))["manifest_sha256"] == manifest["manifest_sha256"]


def test_extraction_refuses_entries_that_escape(tmp_path):
    archive_path = tmp_path / "evil.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        data = b"x"
        info = tarfile.TarInfo("../escape.txt")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError):
        source.safe_extract(str(archive_path), str(tmp_path / "dest"))
    assert not (tmp_path / "escape.txt").exists()


def test_extraction_refuses_links(tmp_path):
    archive_path = tmp_path / "link.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("shortcut")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        archive.addfile(info)
    with pytest.raises(ValueError):
        source.safe_extract(str(archive_path), str(tmp_path / "dest"))


def test_compare_manifests_lists_added_removed_changed():
    old = {"files": {"a": {"sha256": "1"}, "b": {"sha256": "2"}, "c": {"sha256": "3"}}}
    new = {"files": {"a": {"sha256": "1"}, "b": {"sha256": "9"}, "d": {"sha256": "4"}}}
    assert source.compare_manifests(old, new) == {"added": ["d"], "removed": ["c"], "changed": ["b"]}
