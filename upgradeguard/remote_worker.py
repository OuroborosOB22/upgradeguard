import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time

from .source import safe_extract

WORKER_VERSION = "1"
JOB_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,99}")
ROOT = re.compile(r"/[A-Za-z0-9_./-]{1,200}")
MAX_ARCHIVE_BYTES = 500 * 1024 * 1024


def fail(message, code=2):
    print(json.dumps({"error": message}))
    sys.exit(code)


def job_dir(root, job):
    if not ROOT.fullmatch(root) or ".." in root.split("/"):
        fail("bad root")
    if not JOB_ID.fullmatch(job):
        fail("bad job id")
    return os.path.join(root, job)


def capabilities(root):
    os.makedirs(root, exist_ok=True)
    usage = shutil.disk_usage(root)
    return {"worker_version": WORKER_VERSION, "python": "%d.%d.%d" % sys.version_info[:3], "platform": sys.platform,
            "disk_free_mb": usage.free // (1024 * 1024)}


def init(folder):
    os.makedirs(folder, mode=0o700, exist_ok=True)
    return {"ready": True}


def prepare(folder):
    archive = os.path.join(folder, "source.tar.gz")
    if not os.path.isfile(archive) or os.path.getsize(archive) > MAX_ARCHIVE_BYTES:
        fail("no usable source archive")
    target = os.path.join(folder, "source")
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(target)
    try:
        safe_extract(archive, target)
    except (ValueError, tarfile.TarError) as problem:
        fail("the archive was refused: %s" % problem)
    return {"prepared": True}


def start(folder):
    if not os.path.isdir(os.path.join(folder, "source")) or not os.path.isfile(os.path.join(folder, "request.json")):
        fail("the job was not prepared")
    for name in ("exit", "pid"):
        if os.path.exists(os.path.join(folder, name)):
            os.remove(os.path.join(folder, name))
    shutil.rmtree(os.path.join(folder, "out"), ignore_errors=True)
    process = subprocess.Popen([sys.executable, "-m", "upgradeguard.remote_worker", "_run", folder], start_new_session=True,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(os.path.join(folder, "pid"), "w") as handle:
        handle.write(str(process.pid))
    return {"started": True}


def run_job(folder):
    options = {}
    options_path = os.path.join(folder, "options.json")
    if os.path.isfile(options_path):
        with open(options_path) as handle:
            options = json.load(handle)
    command = [sys.executable, "-m", "upgradeguard", "worker", "--request", os.path.join(folder, "request.json"), "--source", os.path.join(folder, "source"),
               "--out", os.path.join(folder, "work-out"), "--publish", os.path.join(folder, "out"), "--work", os.path.join(folder, "work"),
               "--requirements", options.get("requirements", "requirements.txt")]
    if os.path.isfile(os.path.join(folder, "policy.json")):
        command += ["--policy", os.path.join(folder, "policy.json")]
    if options.get("strict_licences"):
        command.append("--strict-licences")
    if options.get("install_project"):
        command.append("--install-project")
    with open(os.path.join(folder, "stdout.log"), "w") as out, open(os.path.join(folder, "stderr.log"), "w") as err:
        code = subprocess.run(command, stdout=out, stderr=err, stdin=subprocess.DEVNULL).returncode
    with open(os.path.join(folder, "exit"), "w") as handle:
        handle.write(str(code))


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status(folder):
    exit_path, pid_path = os.path.join(folder, "exit"), os.path.join(folder, "pid")
    if os.path.isfile(exit_path):
        code = int(open(exit_path).read().strip() or -1)
        return {"state": "SUCCEEDED" if code == 0 else ("CANCELLED" if code == 130 else "FAILED"), "exit": code}
    if os.path.isfile(pid_path) and alive(int(open(pid_path).read().strip() or 0)):
        return {"state": "RUNNING"}
    return {"state": "FAILED", "exit": -1}


def gone(pid):
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        pass
    return not alive(pid)


def stop_group(pid):
    for stop, wait in ((signal.SIGTERM, 3.0), (signal.SIGKILL, 3.0)):
        try:
            os.killpg(pid, stop)
        except OSError:
            return gone(pid)
        deadline = time.time() + wait
        while time.time() < deadline:
            if gone(pid):
                return True
            time.sleep(0.1)
    return gone(pid)


def cancel(folder):
    pid_path = os.path.join(folder, "pid")
    stopped = False
    if os.path.isfile(pid_path):
        pid = int(open(pid_path).read().strip() or 0)
        if pid > 1:
            stopped = stop_group(pid)
        with open(os.path.join(folder, "exit"), "w") as handle:
            handle.write("130")
    return {"cancelled": True, "confirmed_stopped": stopped}


def package(folder):
    out = os.path.join(folder, "out")
    if not os.path.isdir(out):
        fail("no output")
    for current, folders, names in os.walk(out, followlinks=False):
        if any(os.path.islink(os.path.join(current, entry)) for entry in folders + names):
            fail("links are not allowed in the output")
    target = os.path.join(folder, "out.tar.gz")
    with tarfile.open(target, "w:gz") as archive:
        for name in sorted(os.listdir(out)):
            archive.add(os.path.join(out, name), arcname=name)
    return {"packaged": True, "bytes": os.path.getsize(target)}


def cleanup(folder):
    shutil.rmtree(folder, ignore_errors=True)
    return {"cleaned": True}


JOB_COMMANDS = {"init": init, "prepare": prepare, "start": start, "status": status, "cancel": cancel, "package": package, "cleanup": cleanup}


def main(argv=None):
    words = list(sys.argv[1:] if argv is None else argv)
    if words[:1] == ["_run"] and len(words) == 2:
        run_job(words[1])
        return 0
    if len(words) < 3 or words[0] != "--root":
        fail("usage: --root <dir> <command> [job]")
    root, command = words[1], words[2]
    if command == "capabilities":
        print(json.dumps(capabilities(root)))
        return 0
    if command not in JOB_COMMANDS or len(words) != 4:
        fail("unknown command")
    print(json.dumps(JOB_COMMANDS[command](job_dir(root, words[3]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
