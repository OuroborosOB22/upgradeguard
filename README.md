<p align="center"><img src="web/static/logo.png" width="120" alt="UpgradeGuard logo"></p>

# UpgradeGuard

Find out if upgrading one Python package will break your project, before you do it.

Planning presentation: https://ouroborosob22.github.io/upgradeguard/

## What it does

You give it a project, a package, the version you use now and the version you want.

1. It builds a clean environment with the current version.
2. It builds a second clean environment with only that one package changed.
3. It runs your own tests in both, and checks conflicts, known vulnerabilities and licences.
4. It compares the two and answers **Accept**, **Reject** or **Insufficient Evidence**.

Anything that differs between the two environments was caused by the upgrade, so that difference is the evidence. Every reason points to a saved file (install logs, exact versions, test reports) that you can open. A tests-already-failing case is ignored; only tests that passed before and fail after count.

A language model never decides the answer.

## Try it

```
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt

# an upgrade that is safe
./.venv/bin/python -m upgradeguard run --repo examples/demo_repo --package requests --from 2.28.2 --to 2.32.5

# an upgrade that breaks the project
./.venv/bin/python -m upgradeguard run --repo examples/demo_repo --package jinja2 --from 3.0.3 --to 3.1.6
```

The result goes into `evidence/<run id>/` with a readable `report.html`. The exit code is 0 for Accept, 1 for Reject, 2 for Insufficient Evidence and 3 if the tool itself could not run.

## The website

```
./.venv/bin/python -m web.app
```

Open http://127.0.0.1:5057. The front page explains the idea, and **Start** opens the tool at `/app`. There you can run an upgrade check, check a `requirements.txt` for problems ("Dependency health"), and see earlier results under History.

The site only accepts projects under `examples/`, checks every input, uses CSRF tokens, limits how many checks one visitor can start and never shows file paths or stack traces. Set `UPGRADEGUARD_ACCESS_TOKEN` to turn on a login.

## More things it can do

- **Health report**: reads a requirements file without installing anything and scores it (invalid lines, duplicates, version conflicts, denied licences).
- **Snapshots**: `snapshot-run`, `compare` and `recover` remember when a project last passed and show what changed since.
- **Explain the verdict with Ollama**: the result page can explain why an upgrade was rejected using the local Ollama OpenAI-compatible endpoint (`http://127.0.0.1:11434/v1`) and model `llama3.2:3b` by default. The explanation page previews the evidence and asks for confirmation before sending it to the local model. The model explains recorded evidence; it never decides or changes the verdict. To use another endpoint/model, set `UPGRADEGUARD_EXPLAIN_URL` and `UPGRADEGUARD_EXPLAIN_MODEL` before starting the web server. If Ollama is not running or the model is unavailable, UpgradeGuard falls back to a report-based explanation and records why the model could not be used.
- **Python interpreter path**: the local check form defaults to the interpreter running the web app. You can paste an absolute path to another Python executable; the path must exist and point to Python. Remote checks use the remote machine's command name instead of a local path.
- **Your own server**: a check can run on a Linux server over SSH. Servers are set up in a file on the machine that runs the site (`UPGRADEGUARD_REMOTE_PROFILES`, example in `config/remote.example.json`), never from the browser.
- **Docker runner**: `--runner container` runs the whole check in a locked-down container.
- **CI**: `.github/workflows/upgradeguard.yml` runs a check and fails the job when the upgrade is rejected. `.github/workflows/tests.yml` runs the tool's tests and scans our own requirements for known vulnerabilities on every push and pull request.

## How well does it work

We wrote the expected answer for 59 upgrade cases from 25 open source projects before running anything, then compared with three simpler tools.

| method | accuracy | wrongly approved | wrongly rejected |
| --- | --- | --- | --- |
| UpgradeGuard | 100% | 0 | 0 |
| `pip check` only | 71% | 14 | 0 |
| `pip-audit` only | 56% | 23 | 0 |
| a static file check | 68% | 11 | 5 |

These are the results of the latest full run, made on 25 October 2026 with the current code (including the health report, the newer licence rules and the server runner): `benchmark/results.md`. The earlier runs are kept beside it (`results.run1`, `run2`, `run3`). Three cases were meant to end as Insufficient Evidence and did. To run it again: `upgradeguard fetch-repos`, then `upgradeguard benchmark`.

## Tests

```
./.venv/bin/python -m pip install pytest
./.venv/bin/python -m pytest tests          # a few seconds
./.venv/bin/python -m pytest tests --slow   # also builds real environments and uses Docker
```

## Honest limits

- A passing test suite does not prove an upgrade is safe in production.
- The SSH runner has only been tested against a stand-in server, and the explanation feature only against a fake model endpoint.
- The site has not been deployed anywhere public. Before it is, the checklist is: turn on `UPGRADEGUARD_ACCESS_TOKEN`, put it behind HTTPS, and run only approved sample projects.
- The container runner protects your machine from the project's code, but it cannot make the result of a hostile project trustworthy. The container keeps network access while it runs, because installing the packages needs it, so tests run with the network on too.
- Python projects with `requirements.txt` and `pytest` only.

## Team

Gurman Singh (1024030140), Madhur Tuteja (1024030145), Paryag (1024030125).
