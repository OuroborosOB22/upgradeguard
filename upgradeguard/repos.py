import os
import shutil

from .util import read_json, run_command, write_json

REQUIREMENTS_NAME = "requirements.benchmark.txt"


def repo_slug(name):
    return name.replace("/", "__")


def load_repo_entries(repos_path):
    return read_json(repos_path).get("repositories", [])


def current_commit(destination):
    if not os.path.isdir(os.path.join(destination, ".git")):
        return ""
    return run_command(["git", "rev-parse", "HEAD"], cwd=destination, timeout=60)["output"].strip()


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


def fetch_repos(repos_path, destination_root, requirements_dir, only=None, reclone=False):
    lock_path = os.path.join(os.path.dirname(os.path.abspath(repos_path)), "repos.lock.json")
    known = read_json(lock_path) if os.path.isfile(lock_path) else {}
    locked = {}
    for entry in load_repo_entries(repos_path):
        if entry.get("status") == "dropped":
            continue
        if only and entry["name"] not in only:
            continue
        destination = os.path.join(destination_root, repo_slug(entry["name"]))
        previous = known.get(entry["name"], {})
        reusable = not reclone and previous.get("ref") == entry["ref"] and current_commit(destination) == previous.get("commit")
        commit = previous["commit"] if reusable else clone_repo(entry, destination)
        place_requirements(entry, destination, requirements_dir)
        locked[entry["name"]] = {"ref": entry["ref"], "commit": commit}
        print("%s %s at %s" % ("kept" if reusable else "fetched", entry["name"], commit[:10]))
    return locked


def command_fetch_repos(args):
    locked = fetch_repos(args.repos, args.dest, args.requirements_dir, set(args.only) if args.only else None, args.reclone)
    lock_path = os.path.join(os.path.dirname(os.path.abspath(args.repos)), "repos.lock.json")
    existing = read_json(lock_path) if os.path.isfile(lock_path) else {}
    existing.update(locked)
    write_json(lock_path, existing)
    return 0
