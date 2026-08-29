import os
import shutil
import sys
import time

from .metadata import read_installed_packages, site_packages_dir
from .util import run_command, write_text


def interpreter_path(env_dir):
    unix = os.path.join(env_dir, "bin", "python")
    if os.path.exists(unix):
        return unix
    return os.path.join(env_dir, "Scripts", "python.exe")


def create_environment(python_bin, env_dir, log_path):
    if os.path.isdir(env_dir):
        shutil.rmtree(env_dir)
    os.makedirs(env_dir, exist_ok=True)
    return run_command([python_bin, "-m", "venv", env_dir], log_path=log_path, timeout=300)


def pip_install(env_dir, arguments, log_path, use_cache=True, timeout=1800):
    command = [interpreter_path(env_dir), "-m", "pip", "install", "--disable-pip-version-check", "--no-input"]
    if not use_cache:
        command.append("--no-cache-dir")
    command.extend(arguments)
    return run_command(command, log_path=log_path, timeout=timeout)


def pip_freeze(env_dir, log_path):
    return run_command(
        [interpreter_path(env_dir), "-m", "pip", "freeze", "--all"],
        log_path=log_path,
        timeout=300,
    )


def build_environment(side, env_dir, requirement_lines, output_dir, python_bin,
                      test_runner="pytest", use_cache=True, install_timeout=1800):
    started = time.time()
    os.makedirs(output_dir, exist_ok=True)
    install_log = os.path.join(output_dir, "install.log")
    requirements_path = os.path.join(output_dir, "requirements.used.txt")
    write_text(requirements_path, "\n".join(requirement_lines) + "\n")

    result = {
        "side": side,
        "env_dir": env_dir,
        "python_bin": python_bin,
        "requirements_path": requirements_path,
        "install_log": install_log,
        "created": False,
        "installed": False,
        "runner_installed": False,
        "ok": False,
        "failure_stage": "",
        "failure_output": "",
        "freeze": [],
        "packages": [],
        "site_packages": "",
        "duration": 0.0,
    }

    creation = create_environment(python_bin, env_dir, install_log)
    if creation["returncode"] != 0:
        result["failure_stage"] = "venv-create"
        result["failure_output"] = tail(creation["output"])
        result["duration"] = round(time.time() - started, 2)
        return result
    result["created"] = True

    install = pip_install(env_dir, ["-r", requirements_path], install_log, use_cache, install_timeout)
    if install["returncode"] != 0:
        result["failure_stage"] = "dependency-install"
        result["failure_output"] = tail(install["output"])
        result["duration"] = round(time.time() - started, 2)
        return result
    result["installed"] = True

    if test_runner:
        runner = pip_install(env_dir, [test_runner], install_log, use_cache, 900)
        result["runner_installed"] = runner["returncode"] == 0
        if not result["runner_installed"]:
            result["failure_stage"] = "test-runner-install"
            result["failure_output"] = tail(runner["output"])

    frozen = pip_freeze(env_dir, install_log)
    if frozen["returncode"] == 0:
        result["freeze"] = [line.strip() for line in frozen["output"].splitlines() if line.strip()]
        write_text(os.path.join(output_dir, "freeze.txt"), "\n".join(result["freeze"]) + "\n")

    packages = read_installed_packages(env_dir)
    result["packages"] = packages
    result["site_packages"] = site_packages_dir(env_dir)
    result["ok"] = result["installed"] and result["runner_installed"]
    result["duration"] = round(time.time() - started, 2)
    return result


def tail(text, lines=40):
    parts = [line for line in text.splitlines() if line.strip()]
    return "\n".join(parts[-lines:])


def resolve_python(preferred):
    if preferred and shutil.which(preferred):
        return shutil.which(preferred)
    if preferred and os.path.exists(preferred):
        return preferred
    for candidate in ("python3.13", "python3.12", "python3.11", "python3"):
        found = shutil.which(candidate)
        if found:
            return found
    return sys.executable
