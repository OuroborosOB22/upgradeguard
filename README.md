# UpgradeGuard

Evidence based dependency upgrade and licence policy verifier for Python projects.

**Planning presentation:** https://ouroborosob22.github.io/upgradeguard/

## The question we are answering

If a developer upgrades one important dependency, can the project still be built,
tested and distributed safely?

Most tools answer that by reading package files. We answer it by actually doing the
upgrade twice, in two clean environments, and comparing what really happened.

## How it works

For one proposed upgrade we:

1. build a clean environment on the versions the project uses today
2. build a second clean environment with only that one package changed
3. record the full direct and transitive dependency graph on both sides
4. keep the install logs and the exact resolved versions
5. check dependency conflicts, known vulnerabilities and a licence policy you write
6. run the project's own test suite in both environments
7. report only the failures that are new after the upgrade
8. return Accept, Reject or Insufficient Evidence, with every reason pointing at a
   real file we produced

Anything that differs between the two environments was caused by the upgrade. That
difference is the evidence.

## Install

```
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Use it from the terminal

A safe upgrade:

```
./.venv/bin/python -m upgradeguard run \
  --repo examples/demo_repo \
  --package requests --from 2.28.2 --to 2.32.5 \
  --policy policies/default.json
```

An upgrade that breaks the project:

```
./.venv/bin/python -m upgradeguard run \
  --repo examples/demo_repo \
  --package jinja2 --from 3.0.3 --to 3.1.6 \
  --policy policies/default.json
```

Useful flags:

| flag | what it does |
| --- | --- |
| `--policy` | which licence policy file to apply |
| `--strict-licences` | also block when the final environment breaks the policy, even if the upgrade did not cause it |
| `--offline` | skip the online advisory service and use the small bundled list |
| `--no-cache` | make pip download everything again |
| `--python` | which interpreter to build the environments with |
| `--test-timeout` | how long the test suite may run |

Exit codes are `0` for Accept, `1` for Reject and `2` for Insufficient Evidence, so a
pipeline can act on the result directly.

## Use it from the website

```
./.venv/bin/python web/app.py
```

Then open http://127.0.0.1:5057. Fill in the project folder, the package and the two
versions. The page shows progress while the run happens, then the verdict, the
reasons and a download link for the whole evidence folder.

We do not use port 5000 because macOS already uses it for AirPlay.

The website only accepts projects that sit under `examples/`, and run ids are checked
before we touch the filesystem, so a crafted form value or URL cannot reach a folder
outside the evidence directory. Set `UPGRADEGUARD_REPO_BASE` to allow one more folder.
The debugger stays off unless you set `UPGRADEGUARD_DEBUG=1`, and the server binds to
localhost by default.

## Use it in CI

`.github/workflows/upgradeguard.yml` runs a check on demand, uploads the evidence as
a build artifact, and fails the job when the upgrade is rejected.

## What lands in the evidence folder

```
evidence/<run id>/
  run.json          what was asked for
  policy.json       the licence policy that was applied
  verdict.json      the decision and the reason for it
  diff.json         everything that changed between the two environments
  report.html       a readable report you can open in a browser
  before/  after/
    install.log            every pip command and its output
    requirements.used.txt  the exact input for that side
    freeze.txt             the exact resolved versions
    graph.json             the dependency graph
    conflicts.txt          what pip check said
    licenses.json          every package, its licence and the policy result
    audit.json             the vulnerability scan
    junit.xml              the raw test results
    pytest.log             the test output
```

## How the verdict is decided

| situation | verdict |
| --- | --- |
| the current version does not even build | Insufficient Evidence |
| the proposed version does not build | Reject |
| the tests cannot run on one side | Insufficient Evidence |
| a new dependency conflict appears | Reject |
| a new known vulnerability appears | Reject |
| the upgrade adds a package the policy denies | Reject |
| a test passed before and fails after | Reject |
| none of the above | Accept |

A regression means a test that passed before and does not pass after. A test that was
already failing before does not count, and neither does a test that never existed.
That distinction is the whole reason we build two environments instead of one.

## Benchmark

```
./.venv/bin/python -m upgradeguard benchmark --cases benchmark/cases.json
```

We write the expected answer down before we run the tool. See
`benchmark/GROUND_TRUTH.md` for how we choose it. Current state, five cases:

| measure | value |
| --- | --- |
| cases | 5 |
| verdict accuracy | 1.0 |
| wrongly approved upgrades | 0 |
| wrongly rejected upgrades | 0 |
| average time per check | about 11 seconds |

Five cases is a starting point. The plan is 20 to 25 real repositories, listed in
`benchmark/repos.json`.

## Isolation

Each side gets its own virtual environment and its own copy of the project, both
created under `work/`. The two runs never share an interpreter, an installed package
or a working folder, and the tests never run against the original checkout. Every
command we run has a timeout. We do not import the project's code into our own
process at any point.

## What we are not building

No automatic code repair. No other languages. No support for every packaging tool
that exists. And no language model decides the verdict; it can only rephrase a
finished report.

## Layout

```
upgradeguard/     the tool
  spec.py         the request and the licence policy
  venvs.py        builds the clean environments
  metadata.py     reads installed package metadata
  graph.py        builds and compares dependency graphs
  checks/         conflicts, vulnerabilities, licences
  tests_run.py    runs pytest and reads the results
  verdict.py      the decision rules
  report.py       the evidence bundle and html report
  runner.py       ties one run together
  cli.py          the command line
policies/         licence policies
examples/         small projects we test against
benchmark/        cases, ground truth and metrics
web/              the website
docs/             the planning presentation
```

## Team

Gurman Singh (1024030140), Madhur Tuteja (1024030145), Paryag (1024030125).
