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
- **Explain changes**: an optional plain-language summary of a finished result. You see exactly what would be shared and confirm it first. It needs a model endpoint that you provide and it never changes the verdict.
- **Your own server**: a check can run on a Linux server over SSH. Servers are set up in a file on the machine that runs the site (`UPGRADEGUARD_REMOTE_PROFILES`, example in `config/remote.example.json`), never from the browser.
- **Docker runner**: `--runner container` runs the whole check in a locked-down container.
- **CI**: `.github/workflows/upgradeguard.yml` runs a check and fails the job when the upgrade is rejected.

## How well does it work

We wrote the expected answer for 59 upgrade cases from 25 open source projects before running anything, then compared with three simpler tools.

| method | accuracy | wrongly approved | wrongly rejected |
| --- | --- | --- | --- |
| UpgradeGuard | 100% | 0 | 0 |
| `pip check` only | 71% | 14 | 0 |
| `pip-audit` only | 56% | 23 | 0 |
| a static file check | 68% | 11 | 5 |

These are the stored results of the last run (`benchmark/results.md`). Three cases were meant to end as Insufficient Evidence and did. The benchmark was not re-run after the health report and the newer licence rules were added. To run it again: `upgradeguard fetch-repos`, then `upgradeguard benchmark`.

## Tests

```
./.venv/bin/python -m pytest tests          # a few seconds
./.venv/bin/python -m pytest tests --slow   # also builds real environments and uses Docker
```

## Honest limits

- A passing test suite does not prove an upgrade is safe in production.
- The SSH runner has only been tested against a stand-in server, and the explanation feature only against a fake model endpoint.
- The site has not been deployed anywhere public.
- The container runner protects your machine from the project's code, but it cannot make the result of a hostile project trustworthy.
- Python projects with `requirements.txt` and `pytest` only.

## Team

Gurman Singh (1024030140), Madhur Tuteja (1024030145), Paryag (1024030125).
