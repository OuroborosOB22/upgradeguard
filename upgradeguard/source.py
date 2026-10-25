import fnmatch
import hashlib
import os
import tarfile

from .util import run_command

EXCLUDED_NAMES = [
    ".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", ".tox", ".mypy_cache", "node_modules",
    "evidence", "work", "snapshots",
]
SECRET_PATTERNS = [".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.p12", "*.pfx", ".netrc", "credentials*"]
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024


class SourceTooLarge(Exception):
    pass


def exclusion_labels():
    return sorted(EXCLUDED_NAMES + SECRET_PATTERNS)


def is_excluded(name):
    if name in EXCLUDED_NAMES or name.endswith((".pyc", ".pyo")):
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_PATTERNS)


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_files(root):
    root = os.path.realpath(root)
    chosen = []
    skipped = []
    for current, folders, names in os.walk(root, followlinks=False):
        folders[:] = sorted(name for name in folders if not is_excluded(name))
        for name in sorted(names):
            full = os.path.join(current, name)
            relative = os.path.relpath(full, root)
            if is_excluded(name):
                continue
            if os.path.islink(full):
                skipped.append((relative, "symlink"))
                continue
            if not os.path.isfile(full):
                continue
            if os.path.getsize(full) > MAX_FILE_BYTES:
                skipped.append((relative, "larger than %d bytes" % MAX_FILE_BYTES))
                continue
            chosen.append(relative)
    return chosen, skipped


def build_manifest(root):
    root = os.path.realpath(root)
    files, skipped = selected_files(root)
    entries = {}
    total = 0
    for relative in files:
        full = os.path.join(root, relative)
        before = os.stat(full)
        total += before.st_size
        if total > MAX_TOTAL_BYTES:
            raise SourceTooLarge("the selected files are larger than %d bytes" % MAX_TOTAL_BYTES)
        digest = file_digest(full)
        after = os.stat(full)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            skipped.append((relative, "changed while it was being read"))
            continue
        entries[relative] = {"sha256": digest, "bytes": before.st_size}
    return {"files": entries, "skipped": sorted(skipped), "total_bytes": total, "manifest_sha256": manifest_digest(entries)}


def manifest_digest(entries):
    digest = hashlib.sha256()
    for relative in sorted(entries):
        digest.update(("%s\0%s\n" % (relative, entries[relative]["sha256"])).encode())
    return digest.hexdigest()


def git_state(root):
    inside = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, timeout=30)
    if inside["returncode"] != 0 or inside["output"].strip() != "true":
        return None, False
    top = run_command(["git", "rev-parse", "--show-toplevel"], cwd=root, timeout=30)["output"].strip()
    if os.path.realpath(top) != os.path.realpath(root):
        return None, False
    commit = run_command(["git", "rev-parse", "HEAD"], cwd=root, timeout=30)
    status = run_command(["git", "status", "--porcelain"], cwd=root, timeout=30)
    if commit["returncode"] != 0:
        return None, False
    return commit["output"].strip(), bool(status["output"].strip())


def describe_source(root):
    manifest = build_manifest(root)
    commit, dirty = git_state(root)
    return {
        "commit": commit,
        "dirty": dirty,
        "manifest_sha256": manifest["manifest_sha256"],
        "snapshot_id": "snap-" + manifest["manifest_sha256"][:12],
        "exclusions": exclusion_labels(),
        "file_count": len(manifest["files"]),
        "skipped": [{"path": path, "reason": reason} for path, reason in manifest["skipped"]],
    }


def write_archive(root, manifest, archive_path):
    root = os.path.realpath(root)
    os.makedirs(os.path.dirname(os.path.abspath(archive_path)), exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        for relative in sorted(manifest["files"]):
            archive.add(os.path.join(root, relative), arcname=relative, recursive=False)
    return archive_path


def safe_extract(archive_path, destination):
    destination = os.path.realpath(destination)
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            target = os.path.realpath(os.path.join(destination, member.name))
            if not (target == destination or target.startswith(destination + os.sep)):
                raise ValueError("archive entry %s leaves the destination" % member.name)
            if not (member.isfile() or member.isdir()):
                raise ValueError("archive entry %s is not a plain file" % member.name)
        for member in members:
            target = os.path.join(destination, member.name)
            if member.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.extractfile(member) as source, open(target, "wb") as sink:
                sink.write(source.read())


def compare_manifests(old, new):
    old_files, new_files = old["files"], new["files"]
    return {
        "added": sorted(set(new_files) - set(old_files)),
        "removed": sorted(set(old_files) - set(new_files)),
        "changed": sorted(name for name in set(old_files) & set(new_files) if old_files[name]["sha256"] != new_files[name]["sha256"]),
    }
