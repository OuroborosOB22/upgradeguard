import os

from ..venvs import interpreter_path
from ..util import run_command, write_text


def check_conflicts(env_dir, output_dir):
    log_path = os.path.join(output_dir, "pip-check.log")
    result = run_command(
        [interpreter_path(env_dir), "-m", "pip", "check"],
        log_path=log_path,
        timeout=300,
    )
    problems = []
    for line in result["output"].splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith("No broken requirements"):
            continue
        if text.startswith("$ ") or text.startswith("exit code"):
            continue
        problems.append(text)

    write_text(os.path.join(output_dir, "conflicts.txt"), "\n".join(problems) + "\n")
    return {
        "clean": result["returncode"] == 0 and not problems,
        "returncode": result["returncode"],
        "problems": problems,
        "log_path": log_path,
    }


def diff_conflicts(before, after):
    before_set = set(before.get("problems", []))
    after_set = set(after.get("problems", []))
    return {
        "introduced": sorted(after_set - before_set),
        "resolved": sorted(before_set - after_set),
        "unchanged": sorted(after_set & before_set),
    }
