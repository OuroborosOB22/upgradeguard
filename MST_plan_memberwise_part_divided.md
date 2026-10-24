# Member 1 Complete Study & Defense Guide
## UpgradeGuard: The Core Engine and Environments

This guide is written specifically for Member 1. If you come from basic C++ and feel nervous about Python, this document translates every concept into C++ terms and walks through every single line of your 5 files.

---

# Table of Contents
1. The 3 Panic Commands in Terminal
2. Python from 0 for a C++ Programmer
3. Big Picture Architecture of Your Part
4. Line-by-Line Breakdown of Your 5 Files
   - File 1: `upgradeguard/__main__.py`
   - File 2: `upgradeguard/cli.py`
   - File 3: `upgradeguard/runner.py`
   - File 4: `upgradeguard/venvs.py`
   - File 5: `upgradeguard/tests_run.py`
5. How to Run and Test Both Demo Cases
6. Professor Evaluation Questions and Word-for-Word Answers
7. Live Code Edits You Might Be Asked to Do

---

# 1. The 3 Panic Commands in Terminal

Keep your terminal open during the demo. If you ever feel lost:

### 1. Find where any concept or word lives (takes 2 seconds)
```bash
grep -rn "WORD" upgradeguard/
```
Examples:
- Professor asks "Where do you run pytest?" -> type `grep -rn "pytest" upgradeguard/`
- Professor asks "Where are the exit codes?" -> type `grep -rn "EXIT_CODES" upgradeguard/`
- Professor asks "Where do you copy the project?" -> type `grep -rn "copy_repository" upgradeguard/`

Say out loud while typing: *"I will grep for that in the codebase."* This is standard developer behavior.

### 2. Instant Undo if you mess up a live edit
```bash
git checkout -- .
```
This restores every file back to its exact working state instantly. Say: *"Let me revert that and re-apply cleanly."*

### 3. Quick syntax check after editing
```bash
./.venv/bin/python -c "import upgradeguard.cli, upgradeguard.runner, upgradeguard.venvs, upgradeguard.tests_run"
```
If you made an indentation error or typo, Python prints the exact line number immediately.

---

# 2. Python from 0 for a C++ Programmer

In C++, you compile code with `g++` into machine binaries. In Python, the `python` program reads `.py` text files directly, compiles them into bytecode, and executes them in an interpreter.

Here is the direct comparison:

| C++ Feature | Python Feature | How it works in our project |
| --- | --- | --- |
| `int x = 5;` | `x = 5` | Variables do not have explicit types. Python knows `5` is an integer at runtime. |
| Blocks `{ ... }` | Indentation (4 spaces) | There are no curly braces. Code indented under a function or `if` belongs to that block. |
| Semicolons `;` | Newline | Statements end when you press Enter. No semicolons needed. |
| `std::vector<string>` | `list`, e.g. `items = ["a", "b"]` | Dynamic array. Add with `items.append("c")`. Size is `len(items)`. |
| `std::map<string, int>` | `dict`, e.g. `d = {"a": 1, "b": 2}` | Hash map. Access with `d["a"]` or `d.get("a", 0)`. |
| `std::set<string>` | `set`, e.g. `s = {"failed", "error"}` | Set of unique elements. Fast lookup with `if "failed" in s:`. |
| `std::pair<T1, T2>` | `tuple`, e.g. `("before", before_lines)` | Fixed immutable pair or group. Cannot be modified after creation. |
| `int main(...)` | `if __name__ == "__main__":` | Code that runs only when the file is executed directly, not when imported. |
| `sys.exit(code)` | `sys.exit(code)` | Terminates the process and sends return code to the operating system (0 = success, non-zero = fail). |
| `system(...)` or `fork()`/`exec()` | `subprocess.run(...)` | Runs an external command (like `pip install` or `pytest`) and captures stdout, stderr, and returncode. |
| `#include <iostream>` | `import os, sys` | Imports libraries or modules. |

### What is a Virtual Environment in physical terms?
In C++, libraries are installed globally in `/usr/lib`. If two projects need different versions of the same library, they conflict.
In Python, a virtual environment (`venv`) is literally just a folder on disk containing:
1. Its own private Python executable (`bin/python`).
2. Its own private package folder (`lib/python3.x/site-packages`).
When we install packages inside this folder, the host system is completely untouched.

---

# 3. Big Picture Architecture of Your Part

As Member 1, your topic is **The Core Engine & Environments**. You own 5 files:
1. `__main__.py`: Package launcher.
2. `cli.py`: User input parsing and terminal output formatting.
3. `runner.py`: Pipeline orchestrator that coordinates everything.
4. `venvs.py`: Sandbox builder that creates clean environments and runs pip.
5. `tests_run.py`: Pytest executor and regression detection algorithm.

### The Pipeline Flow:
```
Terminal: python -m upgradeguard run ...
   │
   ▼
cli.py: parses arguments (--repo, --package, --from, --to)
   │
   ▼
runner.py: coordinates the upgrade check
   ├── Step 1: creates work/ and evidence/ folders
   ├── Step 2: reads requirements.txt and pins old vs new versions
   │
   ├── Step 3 (BEFORE ENVIRONMENT):
   │     ├── venvs.py: creates clean venv in work/.../before/env
   │     ├── venvs.py: pip install requirements with old version
   │     ├── venvs.py: pip install pytest
   │     ├── venvs.py: pip freeze > freeze.txt
   │     ├── [Member 2 checks: conflicts, vulns, licenses]
   │     └── tests_run.py: runs pytest in before environment, saves junit.xml
   │
   ├── Step 4 (AFTER ENVIRONMENT):
   │     ├── venvs.py: creates clean venv in work/.../after/env
   │     ├── venvs.py: pip install requirements with new version
   │     ├── venvs.py: pip install pytest
   │     ├── venvs.py: pip freeze > freeze.txt
   │     ├── [Member 2 checks: conflicts, vulns, licenses]
   │     └── tests_run.py: runs pytest in after environment, saves junit.xml
   │
   ├── Step 5: diffs before vs after (finds regressions in tests_run.py)
   ├── Step 6: passes diff to verdict.py to get Accept / Reject / Insufficient
   └── Step 7: writes report.html, bundle.json, and prints summary in cli.py
```

---

# 4. Line-by-Line Breakdown of Your 5 Files

---

## File 1: `upgradeguard/__main__.py` (7 lines)

### Complete Code:
```python
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
```

### Explanation:
- `import sys`: imports Python system utilities, including `sys.exit`.
- `from .cli import main`: imports the `main` function from `cli.py` in the same directory (the dot means current package).
- `if __name__ == "__main__":`:
  When you execute `python -m upgradeguard`, Python sets a special built-in variable `__name__` equal to `"__main__"`. If another file imports this file, `__name__` would be `"upgradeguard.__main__"`. This `if` check ensures the code runs only when launched from the terminal.
- `sys.exit(main())`: calls `main()`, gets its integer return code (0, 1, or 2), and exits the program with that return code.

---

## File 2: `upgradeguard/cli.py` (116 lines)

### Purpose:
Parses command-line flags, converts user inputs into an `UpgradeSpec` configuration object, runs the upgrade pipeline, and prints the colored terminal summary.

### Section 1: Exit Codes and Imports (Lines 1 to 10)
```python
import argparse
import os
import sys

from .runner import run_upgrade_check
from .spec import UpgradeSpec, load_policy
from .verdict import ACCEPT, INSUFFICIENT, REJECT

EXIT_CODES = {ACCEPT: 0, REJECT: 1, INSUFFICIENT: 2}
```
- `argparse`: standard library module to handle CLI flags.
- `EXIT_CODES`: a dictionary mapping verdict strings to standard Unix exit codes:
  - `ACCEPT -> 0` (success in shell / CI passes)
  - `REJECT -> 1` (failure / CI fails the build)
  - `INSUFFICIENT -> 2` (cannot determine evidence, e.g. base repo broken)

### Section 2: Building the Argument Parser (Lines 12 to 44)
```python
def build_parser():
    parser = argparse.ArgumentParser(
        prog="upgradeguard",
        description="Check one Python dependency upgrade by building and testing it twice",
    )
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("run", help="check a single proposed upgrade")
    check.add_argument("--repo", required=True)
    check.add_argument("--package", required=True)
    check.add_argument("--from", dest="from_version", required=True)
    check.add_argument("--to", dest="to_version", required=True)
    check.add_argument("--policy", default="policies/default.json")
    check.add_argument("--python", dest="python_bin", default="python3")
    check.add_argument("--requirements", default="requirements.txt")
    check.add_argument("--evidence", default="evidence")
    check.add_argument("--work", default="work")
    check.add_argument("--label", default="")
    check.add_argument("--offline", action="store_true")
    check.add_argument("--no-cache", dest="no_cache", action="store_true")
    check.add_argument("--test-timeout", type=int, default=900)
    check.add_argument("--strict-licences", dest="strict_licences", action="store_true")
    check.add_argument("--quiet", action="store_true")
```
- `subparsers`: allows multiple commands like `upgradeguard run` and `upgradeguard benchmark`.
- `--repo`: path to the project to test (e.g. `examples/demo_repo`).
- `--package`: name of package to upgrade (e.g. `requests` or `jinja2`).
- `--from`: existing version string (e.g. `2.28.2`).
- `--to`: target version string (e.g. `2.32.5`).
- `--policy`: path to license rules JSON file.
- `--python`: base python interpreter to clone for the venvs.
- `--offline`: skips network requests (uses local vulnerability database).
- `--test-timeout`: maximum seconds before pytest is killed (default 900s = 15 min).

### Section 3: Main and Run Command (Lines 46 to 85)
```python
def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return command_run(args)
    if args.command == "benchmark":
        from .benchmark import command_benchmark
        return command_benchmark(args)
    parser.print_help()
    return 2

def command_run(args):
    spec = UpgradeSpec(
        repo_path=args.repo,
        package=args.package,
        from_version=args.from_version,
        to_version=args.to_version,
        python_bin=args.python_bin,
        policy_path=args.policy,
        requirements_file=args.requirements,
        label=args.label,
    )
    policy = load_policy(args.policy if os.path.isfile(args.policy) else "")
    reporter = None if args.quiet else progress_line

    bundle = run_upgrade_check(
        spec,
        policy,
        evidence_root=args.evidence,
        work_root=args.work,
        allow_network=not args.offline,
        use_cache=not args.no_cache,
        test_timeout=args.test_timeout,
        strict_licences=args.strict_licences,
        progress=reporter,
    )
    print_summary(bundle)
    return EXIT_CODES.get(bundle["verdict"]["decision"], 2)
```
- Creates an `UpgradeSpec` object holding user inputs.
- Calls `run_upgrade_check(...)` from `runner.py` to execute the whole pipeline.
- Calls `print_summary(bundle)` to display results.
- Returns the exit code (0, 1, or 2).

### Section 4: Output Formatting (Lines 87 to 112)
```python
def progress_line(message):
    sys.stderr.write("  %s\n" % message)
    sys.stderr.flush()

def print_summary(bundle):
    verdict = bundle["verdict"]
    diff = bundle["diff"]
    print("")
    print(verdict["headline"])
    print("-" * len(verdict["headline"]))
    for item in verdict["reasons"]:
        print("  [%s] %s" % (item["code"], item["message"]))
    for item in verdict["notes"]:
        print("  (%s) %s" % (item["code"], item["message"]))
    print("")
    print("dependency changes : %d added, %d removed, %d version changes" % (
        len(diff["graph"]["added"]), len(diff["graph"]["removed"]), len(diff["graph"]["changed"])))
    print("test regressions   : %d" % len(diff["tests"]["regressions"]))
    print("new conflicts      : %d" % len(diff["conflicts"]["introduced"]))
    print("new vulnerabilities: %d" % len(diff["vulnerabilities"]["introduced"]))
    print("licence violations : %d new" % len(diff["licenses"]["introduced"]))
    print("evidence           : %s" % bundle["evidence_dir"])
    print("report             : %s" % os.path.join(bundle["evidence_dir"], "report.html"))
    print("total time         : %ss" % bundle["total_seconds"])
```
- Writes progress steps to `stderr` so machine consumers can read pure output from `stdout`.
- Prints reasons (blocking items that cause Reject) and notes (informational items).
- Prints counts of dependency changes, test regressions, conflicts, and the link to `report.html`.

---

## File 3: `upgradeguard/runner.py` (127 lines)

### Purpose:
The engine orchestrator. It manages directories, prepares requirements, executes the before and after builds, gathers all evidence, and produces the final bundle.

### Step-by-step walkthrough:

#### 1. Setup and Directory Creation (Lines 17 to 33)
```python
def run_upgrade_check(spec, policy, evidence_root="evidence", work_root="work",
                      allow_network=True, use_cache=True, test_timeout=900,
                      install_timeout=1800, strict_licences=False, progress=None):
    started = time.time()
    if not spec.run_id:
        spec.run_id = new_run_id(spec)

    repo_path = os.path.abspath(spec.repo_path)
    requirements_path = os.path.join(repo_path, spec.requirements_file)
    if not os.path.isfile(requirements_path):
        raise FileNotFoundError("no %s found in %s" % (spec.requirements_file, repo_path))

    evidence_dir = os.path.abspath(os.path.join(evidence_root, spec.run_id))
    work_dir = os.path.abspath(os.path.join(work_root, spec.run_id))
    os.makedirs(evidence_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)
```
- `new_run_id`: creates a unique run folder name, e.g. `20260916-225925-requests-2_28_2-to-2_32_5`.
- Creates `evidence/<run_id>` for permanent artifacts (HTML report, JSON logs).
- Creates `work/<run_id>` for scratch virtual environments.

#### 2. Requirement Pinning (Lines 34 to 41)
```python
    python_bin = resolve_python(spec.python_bin)
    base_lines = read_requirements(requirements_path)
    direct = set(declared_names(base_lines))

    before_lines, before_found = pin_package(base_lines, spec.package, spec.from_version)
    after_lines, after_found = pin_package(base_lines, spec.package, spec.to_version)
    direct.add(spec.normalised_package())
```
- Reads the existing `requirements.txt`.
- `pin_package` modifies the file lines in memory:
  - In `before_lines`, it pins the package to `from_version` (e.g. `jinja2==3.0.3`).
  - In `after_lines`, it pins the package to `to_version` (e.g. `jinja2==3.1.6`).
- Everything else in the requirements list remains identical.

#### 3. Building and Checking Both Sides (Lines 42 to 82)
```python
    sides = {}
    for side, lines in (("before", before_lines), ("after", after_lines)):
        announce(progress, "building %s environment" % side)
        side_dir = os.path.join(evidence_dir, side)
        env_dir = os.path.join(work_dir, side, "env")
        repo_copy = copy_repository(repo_path, os.path.join(work_dir, side, "repo"))
        build = build_environment(
            side, env_dir, lines, side_dir, python_bin,
            use_cache=use_cache, install_timeout=install_timeout,
        )
```
- Loops through `"before"` then `"after"`.
- `copy_repository`: copies the user's project into `work/<run_id>/<side>/repo`. Why? So pytest never creates `.pytest_cache` in the user's directory and never mutates their project.
- `build_environment`: builds the isolated sandbox in `env_dir`.
- Builds dependency graph and writes `graph.json`.
- If the environment built successfully:
  - Checks for dependency conflicts with `check_conflicts` (`pip check`).
  - Checks for known vulnerabilities with `audit_environment` (`pip-audit`).
  - Checks licenses against policy with `check_licenses`.
  - Runs the test suite with `run_test_suite` (`pytest`).
- Saves `summary.json` containing all data for that side.

#### 4. Comparison and Verdict (Lines 83 to 116)
```python
    announce(progress, "comparing both environments")
    difference = {
        "graph": diff_graphs(sides["before"]["graph"], sides["after"]["graph"]),
        "conflicts": diff_conflicts(sides["before"]["conflicts"], sides["after"]["conflicts"]),
        "vulnerabilities": diff_vulnerabilities(sides["before"]["vulnerabilities"], sides["after"]["vulnerabilities"]),
        "licenses": diff_licenses(sides["before"]["licenses"], sides["after"]["licenses"]),
        "tests": diff_test_runs(sides["before"]["tests"], sides["after"]["tests"]),
    }
```
- Diffs all components between before and after.
- Diffs tests with `diff_test_runs` to spot test regressions.
- Calls `decide(bundle)` from `verdict.py` to calculate verdict.
- Writes `run.json`, `diff.json`, `verdict.json`, `bundle.json`, and `report.html`.

---

## File 4: `upgradeguard/venvs.py` (129 lines)

### Purpose:
Creates and manages clean virtual environments ("sandboxes"), executes pip install commands, and clones the repository.

### Functions walkthrough:

#### 1. `interpreter_path(env_dir)` (Lines 15 to 19)
```python
def interpreter_path(env_dir):
    unix = os.path.join(env_dir, "bin", "python")
    if os.path.exists(unix):
        return unix
    return os.path.join(env_dir, "Scripts", "python.exe")
```
- Locates the private Python binary inside the virtual environment directory.
- On macOS and Linux, it lives at `<env_dir>/bin/python`.
- On Windows, it lives at `<env_dir>/Scripts/python.exe`.

#### 2. `create_environment(python_bin, env_dir, log_path)` (Lines 22 to 26)
```python
def create_environment(python_bin, env_dir, log_path):
    if os.path.isdir(env_dir):
        shutil.rmtree(env_dir)
    os.makedirs(env_dir, exist_ok=True)
    return run_command([python_bin, "-m", "venv", env_dir], log_path=log_path, timeout=300)
```
- Cleans up any existing folder at `env_dir` to ensure a 100% clean state.
- Executes `python3 -m venv <env_dir>` via `run_command` (which uses Python's `subprocess.run`).
- Writes full creation output to `install_log`.

#### 3. `pip_install(...)` and `pip_freeze(...)` (Lines 29 to 43)
```python
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
```
- Always calls pip via the environment's own python: `[interpreter_path, "-m", "pip", ...]`.
- Uses `--no-input` so pip never freezes waiting for a prompt if a package is missing.
- Uses `--disable-pip-version-check` to keep logs clean.
- `pip_freeze` exports all installed packages with exact versions to provide forensic evidence.

#### 4. `build_environment(...)` (Lines 45 to 104)
```python
def build_environment(side, env_dir, requirement_lines, output_dir, python_bin,
                      test_runner="pytest", use_cache=True, install_timeout=1800):
```
- Writes requirement lines to `requirements.used.txt`.
- Step 1: runs `create_environment`. If returncode != 0, sets `failure_stage = "venv-create"` and returns.
- Step 2: runs `pip_install` with `-r requirements.used.txt`. If returncode != 0, sets `failure_stage = "dependency-install"` and returns.
- Step 3: installs `pytest` so the test suite can be run.
- Step 4: runs `pip_freeze` and writes `freeze.txt`.
- Step 5: inspects `site-packages` directory using `read_installed_packages(env_dir)`.
- Returns result dictionary with `ok = True` if installation and pytest installation succeeded.

#### 5. `copy_repository(repo_path, destination)` (Lines 124 to 129)
```python
def copy_repository(repo_path, destination):
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    shutil.copytree(repo_path, destination, ignore=COPY_IGNORE, symlinks=True)
    return destination
```
- Copies target repository using `shutil.copytree`.
- Uses `COPY_IGNORE` to skip `.git`, `.venv`, `__pycache__`, `evidence`, and `work` so we don't copy unnecessary files.

---

## File 5: `upgradeguard/tests_run.py` (143 lines)

### Purpose:
Runs pytest in the sandbox, parses the machine-readable JUnit XML output, and diffs the test results to detect test regressions.

### Section 1: Running the Test Suite (Lines 8 to 36)
```python
def run_test_suite(env_dir, repo_path, output_dir, timeout=900):
    junit_path = os.path.join(output_dir, "junit.xml")
    log_path = os.path.join(output_dir, "pytest.log")
    result = run_command(
        [
            interpreter_path(env_dir), "-m", "pytest",
            "--junitxml", junit_path,
            "-q", "-p", "no:cacheprovider",
            "--continue-on-collection-errors",
            "--rootdir", repo_path,
        ],
        cwd=repo_path,
        log_path=log_path,
        timeout=timeout,
    )

    parsed = parse_junit(junit_path)
    collected = parsed is not None
    return {
        "ran": collected,
        "returncode": result["returncode"],
        "timed_out": result["timed_out"],
        "duration": result["duration"],
        "junit_path": junit_path if collected else "",
        "log_path": log_path,
        "results": parsed or {},
        "counts": count_statuses(parsed or {}),
        "tail": tail_lines(result["output"]),
    }
```

### Why these pytest flags are used (Know these by heart):
1. `--junitxml junit_path`: Pytest normally prints test outcomes to terminal. This flag tells pytest to write a standardized XML file containing each test case, status, and error message.
2. `-q`: Quiet mode to reduce terminal clutter.
3. `-p no:cacheprovider`: Tells pytest not to create or read `.pytest_cache` folders on disk.
4. `--continue-on-collection-errors`: CRITICAL FIX! If one test file has a broken import, pytest by default aborts test collection completely and skips all other test files. This flag forces pytest to continue collecting and running the rest of the test suite!
5. `--rootdir repo_path`: Locks the root directory to the copied repository so pytest does not pick up outer project configuration.

### Section 2: Parsing JUnit XML (Lines 39 to 75)
```python
def parse_junit(path):
    if not os.path.isfile(path):
        return None
    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError:
        return None

    results = {}
    for case in tree.getroot().iter("testcase"):
        identifier = build_identifier(case)
        status = "passed"
        message = ""
        for child in case:
            tag = child.tag
            if tag == "failure":
                status = "failed"
            elif tag == "error":
                status = "error"
            elif tag == "skipped":
                status = "skipped"
            else:
                continue
            message = (child.get("message") or "").strip().split("\n")[0][:300]
            break
        results[identifier] = {"status": status, "message": message, "time": case.get("time", "0")}
    return results
```
- Reads the XML file generated by pytest using `xml.etree.ElementTree`.
- Finds every `<testcase>` element.
- If it has a child tag `<failure>`, status is `"failed"`.
- If it has a child tag `<error>`, status is `"error"`.
- If it has a child tag `<skipped>`, status is `"skipped"`.
- If it has no error tags, status is `"passed"`.
- Formats test name as `tests/test_render.py::test_name`.

### Section 3: The Regression Detection Algorithm (Lines 90 to 143)
```python
def diff_test_runs(before, after):
    before_results = before.get("results", {})
    after_results = after.get("results", {})
    broken = {"failed", "error"}

    regressions = []
    fixed = []
    new_tests = []
    removed_tests = []

    for identifier in sorted(after_results):
        current = after_results[identifier]
        if identifier not in before_results:
            new_tests.append({
                "test": identifier,
                "status": current["status"],
                "message": current["message"],
            })
            continue
        previous = before_results[identifier]
        if previous["status"] == "passed" and current["status"] in broken:
            regressions.append({
                "test": identifier,
                "before": previous["status"],
                "after": current["status"],
                "message": current["message"],
            })
        elif previous["status"] in broken and current["status"] == "passed":
            fixed.append({"test": identifier, "before": previous["status"], "after": "passed"})

    for identifier in sorted(before_results):
        if identifier in after_results:
            continue
        previous = before_results[identifier]
        removed_tests.append({"test": identifier, "status": previous["status"]})
        if previous["status"] == "passed":
            regressions.append({
                "test": identifier,
                "before": "passed",
                "after": "not collected",
                "message": "this test passed before the upgrade and could not be collected after it",
            })
```

### The Exact Rules of Regression:
1. **Rule 1**: A test is a regression if it **passed** in the before environment and is **failed** or **error** in the after environment.
2. **Rule 2**: If a test was already failing before the upgrade (`previous["status"] in broken`), it is NOT a regression! The upgrade did not break it.
3. **Rule 3**: If a test passed before, but is missing from after results (because the test file failed to import or was deleted), it is counted as a regression (`"not collected"`).
4. **Rule 4**: If a test failed before and passes after, it is recorded under `fixed`.

---

# 5. How to Run and Test Both Demo Cases

Open your terminal in `~/Documents/Sem5Present/sweProject` and run these exact commands:

### Case 1: Safe Upgrade (Requests) -> Verdict: ACCEPT
```bash
./.venv/bin/python -m upgradeguard run \
  --repo examples/demo_repo \
  --package requests \
  --from 2.28.2 \
  --to 2.32.5
```
**Output you will see:**
```
  building before environment
  checking before environment
  running tests in before environment
  building after environment
  checking after environment
  running tests in after environment
  comparing both environments
  done

Accept: upgrading requests from 2.28.2 to 2.32.5
------------------------------------------------
  [no-blocking-evidence] Both environments built, the test suite ran in both, and no new conflict, vulnerability, licence violation or test regression was found.
  (vulnerabilities-resolved) The upgrade removes 3 known vulnerability finding(s).

dependency changes : 0 added, 0 removed, 2 version changes
test regressions   : 0
new conflicts      : 0
new vulnerabilities: 0
licence violations : 0 new
```
- Exit code: `0`.
- All tests pass in both environments.
- 3 known vulnerabilities are removed.

### Case 2: Unsafe Upgrade (Jinja2) -> Verdict: REJECT
```bash
./.venv/bin/python -m upgradeguard run \
  --repo examples/demo_repo \
  --package jinja2 \
  --from 3.0.3 \
  --to 3.1.6
```
**Output you will see:**
```
Reject: upgrading jinja2 from 3.0.3 to 3.1.6
--------------------------------------------
  [test-regression] 5 test(s) passed before the upgrade and fail after it: tests.test_render::test_plain_body_is_escaped, tests.test_render::test_render_many_joins_notes, tests.test_render::test_title_is_escaped
  (new-failing-tests) 1 test(s) exist only in the upgraded run and are failing there.
  (vulnerabilities-resolved) The upgrade removes 2 known vulnerability finding(s).

dependency changes : 0 added, 0 removed, 1 version changes
test regressions   : 5
new conflicts      : 0
new vulnerabilities: 0
licence violations : 0 new
```
- Exit code: `1`.
- In Jinja2 3.1, `Markup` was removed.
- Exactly 5 tests fail in the after environment that passed before.

### View the Evidence Report in Browser:
```bash
open evidence/*jinja2*/report.html
```
This opens the HTML report showing the full regression table, test failure messages, and dependency diffs.

---

# 6. Professor Evaluation Questions and Word-for-Word Answers

### Question 1: "Why is your project written in Python and not C++?"
**Your answer:**
> "Because the core problem is Python packaging. UpgradeGuard creates Python virtual environments, drives pip install, reads package metadata from site-packages, and executes pytest. If we wrote this in C++, every single step would have to shell out to Python subprocesses anyway, making C++ just an empty wrapper. Writing it in Python gives us direct access to packaging internals."

### Question 2: "What is a virtual environment and why do you build TWO of them instead of ONE?"
**Your answer:**
> "A virtual environment is an isolated directory containing its own Python interpreter and site-packages folder so dependencies do not clash with the system.
> We build two environments (before and after) to establish true causality. If we only tested the upgraded environment, we could not distinguish between a test that broke because of the upgrade and a test that was already broken beforehand. Testing both is what provides proof."

### Question 3: "What is your exact definition of a test regression?"
**Your answer:**
> "In `tests_run.py`, function `diff_test_runs`, a regression is defined as a test whose status was 'passed' in the before environment, but became 'failed', 'error', or uncollected in the after environment. If a test was already failing before the upgrade, it is not counted as a regression."

### Question 4: "Why do you copy the repository to `work/`?"
**Your answer:**
> "We use `copy_repository` in `venvs.py` to copy the project into `work/<run>/<side>/repo`. This guarantees that we never touch or alter the user's original source code. Furthermore, pytest creates `.pytest_cache` files and searches upward for `pyproject.toml`. Copying ensures complete filesystem isolation between the two runs."

### Question 5: "What happens if a test file fails to import during test collection?"
**Your answer:**
> "By default, pytest aborts collection immediately and runs zero tests. We solved this by passing the `--continue-on-collection-errors` flag to pytest in `tests_run.py`. This ensures pytest keeps running the remaining tests and records the broken test file as an error."

---

# 7. Live Code Edits You Might Be Asked to Do

The professor might say: "Open your code, make this change, and run it."

### Edit 1: "Change the default test timeout from 900 seconds to 60 seconds"
- **File:** `upgradeguard/cli.py`, line 32.
- **Find:**
  ```python
  check.add_argument("--test-timeout", type=int, default=900)
  ```
- **Change `900` to `60`:**
  ```python
  check.add_argument("--test-timeout", type=int, default=60)
  ```
- **Test:** Run the command in terminal.

### Edit 2: "Make skipped tests count as regressions"
- **File:** `upgradeguard/tests_run.py`, line 93.
- **Find:**
  ```python
  broken = {"failed", "error"}
  ```
- **Change to:**
  ```python
  broken = {"failed", "error", "skipped"}
  ```
- **Say out loud:** "By default, skipped tests are deliberate, not regressions. Adding 'skipped' to the broken set means any test that passed before but gets skipped after will be flagged as a regression."

### Edit 3: "Add an extra line to the CLI summary output"
- **File:** `upgradeguard/cli.py`, inside `print_summary` around line 105.
- **Add:**
  ```python
  print("python interpreter : %s" % bundle["python_bin"])
  ```
- **Test:** Run the command and observe the extra line printed in terminal!

### Edit 4: "Change the exit codes"
- **File:** `upgradeguard/cli.py`, line 9.
- **Find:**
  ```python
  EXIT_CODES = {ACCEPT: 0, REJECT: 1, INSUFFICIENT: 2}
  ```
- **Change to:**
  ```python
  EXIT_CODES = {ACCEPT: 0, REJECT: 10, INSUFFICIENT: 20}
  ```
- **Say out loud:** "These exit codes are consumed by CI/CD pipelines. 0 is standard Unix success, and non-zero fails the pipeline."

### If anything goes wrong or you make a typo during the evaluation:
```bash
git checkout -- .
```
All files will instantly snap back to working condition.
