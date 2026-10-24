import os
import shutil

from .util import read_json, run_command, write_json

REQUIREMENTS_NAME = "requirements.benchmark.txt"


def repo_slug(name):
    return name.replace("/", "__")


def load_repo_entries(repos_path):
    return read_json(repos_path).get("repositories", [])


def clone_repo(entry, destination):
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    cloned = run_command(
        ["git", "clone", "--quiet", "--depth", "1", "--branch", entry["ref"], entry["url"], destination],
        timeout=600,
    )
    if cloned["returncode"] != 0:
        raise RuntimeError("clone failed for %s: %s" % (entry["name"], cloned["output"].strip()[-300:]))
    head = run_command(["git", "rev-parse", "HEAD"], cwd=destination, timeout=60)
    return head["output"].strip()


def place_requirements(entry, destination, requirements_dir):
    source = os.path.join(requirements_dir, repo_slug(entry["name"]) + ".txt")
    if not os.path.isfile(source):
        raise FileNotFoundError("missing requirements file %s" % source)
    shutil.copyfile(source, os.path.join(destination, REQUIREMENTS_NAME))


def fetch_repos(repos_path, destination_root, requirements_dir, only=None):
    locked = {}
    for entry in load_repo_entries(repos_path):
        if entry.get("status") == "dropped":
            continue
        if only and entry["name"] not in only:
            continue
        destination = os.path.join(destination_root, repo_slug(entry["name"]))
        commit = clone_repo(entry, destination)
        place_requirements(entry, destination, requirements_dir)
        locked[entry["name"]] = {"ref": entry["ref"], "commit": commit}
        print("fetched %s at %s" % (entry["name"], commit[:10]))
    return locked


def command_fetch_repos(args):
    locked = fetch_repos(args.repos, args.dest, args.requirements_dir, set(args.only) if args.only else None)
    lock_path = os.path.join(os.path.dirname(os.path.abspath(args.repos)), "repos.lock.json")
    existing = read_json(lock_path) if os.path.isfile(lock_path) else {}
    existing.update(locked)
    write_json(lock_path, existing)
    return 0
