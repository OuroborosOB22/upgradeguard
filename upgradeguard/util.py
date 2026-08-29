import json
import os
import subprocess
import time


def run_command(args, cwd=None, log_path=None, timeout=1800, env=None):
    started = time.time()
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    try:
        finished = subprocess.run(
            args,
            cwd=cwd,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        code = finished.returncode
        output = finished.stdout + finished.stderr
        timed_out = False
    except subprocess.TimeoutExpired as expired:
        code = -1
        output = (expired.stdout or "") + (expired.stderr or "")
        output += "\nCOMMAND TIMED OUT AFTER %s SECONDS\n" % timeout
        timed_out = True
    except FileNotFoundError as missing:
        code = -1
        output = "COMMAND NOT FOUND: %s\n" % missing
        timed_out = False

    duration = round(time.time() - started, 2)
    if log_path:
        ensure_parent(log_path)
        with open(log_path, "a") as handle:
            handle.write("$ %s\n" % " ".join(args))
            handle.write(output)
            handle.write("\nexit code %s after %ss\n\n" % (code, duration))
    return {
        "args": args,
        "returncode": code,
        "output": output,
        "duration": duration,
        "timed_out": timed_out,
        "log_path": log_path,
    }


def ensure_parent(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def write_json(path, payload):
    ensure_parent(path)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def read_json(path):
    with open(path) as handle:
        return json.load(handle)


def write_text(path, text):
    ensure_parent(path)
    with open(path, "w") as handle:
        handle.write(text)


def relative_to(path, base):
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return path
