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
./.venv/bin/python -m pip install -r requirements.txt
```

## Commands

| command | what it does |
| --- | --- |
| `run` | check one proposed upgrade in two clean environments |
| `run --json` | same, but stdout is one contract v1 evidence document and progress goes to stderr |
| `run --runner container` | same, but the whole run happens inside a locked down Docker container |
| `snapshot-run` | run the tests once and record the result as a snapshot |
| `compare` | compare two snapshots, or today against the last passing one |
| `recover` | try the dependency version from an older snapshot, in separate copies |
| `worker` | run one job described by a contract v1 request file (this is what the container runs) |
| `benchmark` | run every case in `benchmark/cases.json` and score it against three baselines |
| `benchmark-rescore` | recompute the metrics from an existing results file |
| `fetch-repos` | clone the benchmark repositories at their pinned versions |

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

Useful flags for `run`:

| flag | what it does |
| --- | --- |
| `--policy` | which licence policy file to apply |
| `--strict-licences` | also block when the final environment breaks the policy, even if the upgrade did not cause it |
| `--offline` | skip the online advisory service and use the small bundled list |
| `--no-cache` | make pip download everything again |
| `--python` | which interpreter to build the environments with |
| `--test-timeout` | how long the test suite may run |
| `--install-project` | also install the project itself without its dependencies |
| `--pytest-arg` | pass an option to pytest, can be repeated |
| `--json` | print the contract v1 evidence document and nothing else on stdout |
| `--runner container` | run inside Docker (build the image first, see below) |

Exit codes are `0` for Accept, `1` for Reject, `2` for Insufficient Evidence and `3`
when the tool itself could not run, so a pipeline can act on the result directly.

### Snapshots

A snapshot remembers when a project worked: the exact source bytes, the resolved
dependencies, the test results and the environment.

```
./.venv/bin/python -m upgradeguard snapshot-run --repo examples/demo_repo --store snapshots
./.venv/bin/python -m upgradeguard compare --project demo_repo --store snapshots --repo examples/demo_repo
./.venv/bin/python -m upgradeguard recover --repo examples/demo_repo --project demo_repo --snapshot <id> --package jinja2
```

A snapshot is called `PASSING` only when the whole selected test profile ran and passed.
A run with failing tests is `STARTING_ONLY`, a run that could not finish or collected
nothing is `INCONCLUSIVE`. Secrets such as `.env` files and keys are never stored.
Projects can also record snapshots from inside pytest: set
`UPGRADEGUARD_SNAPSHOT_DIR` and run `pytest -p upgradeguard.pytest_plugin`.

## Use it from the website

```
./.venv/bin/python -m web.app
```

Then open http://127.0.0.1:5057. Fill in the project folder, the package and the two
versions. The page shows progress while the run happens, then the verdict, the
reasons and a download link for the whole evidence folder.

We do not use port 5000 because macOS already uses it for AirPlay.

What the website refuses to do: it only accepts projects under `examples/`, checks
package names, versions and interpreters against strict patterns, needs a CSRF token on
every form, limits how many checks one visitor can start, never shows server paths or
stack traces, sets security headers, and removes the working files after each run.
Setting `UPGRADEGUARD_ACCESS_TOKEN` turns on a login. The server will not listen on
anything but localhost without it.

### Hosting it

```
docker build -t upgradeguard-web .
docker run -p 8000:8000 -e UPGRADEGUARD_ACCESS_TOKEN=<choose a long random token> upgradeguard-web
```

The image refuses to start without the token. Put it behind HTTPS before exposing it.
We have built and started this image locally, we have not deployed it anywhere public.

## Use it in CI

`.github/workflows/upgradeguard.yml` runs a check on demand, uploads the evidence as
a build artifact, and fails the job when the upgrade is rejected.

## The container runner

```
docker build -f Dockerfile.runner -t upgradeguard-runner:local .
./.venv/bin/python -m upgradeguard run --repo examples/demo_repo --package jinja2 --from 3.0.3 --to 3.1.6 --runner container
```

Inside the container the project is mounted read only, no host environment variables
are passed in, there is no Docker socket, all capabilities are dropped, the process is
not root, memory, CPU and process counts are limited, and the root file system is
read only. After the job the host stops the container, copies the output without
following links, checks it against the schema, checks every file against the hashes in
the evidence, and only then keeps it.

What this does and does not give you. It protects your machine from the project's code.
It does not make the result trustworthy when the project itself is hostile, because a
hostile test suite runs next to the code that records its results and could lie about
them. Install steps still need network access. So treat it as safe for projects you
chose, not as proof that an unknown project is safe.

## Contract v1

`contracts/v1/` holds the JSON Schemas that the Python tool, the Java project and the ML
project share: request, evidence, snapshot, comparison, worker result and the two
prediction messages. `contracts/v1/check.py` validates every fixture and the recorded
digests. Verdicts inside the tool stay `Accept`, `Reject` and `Insufficient Evidence`;
the contract output uses `ACCEPT`, `REJECT` and `INSUFFICIENT_EVIDENCE`.

## What lands in the evidence folder

```
evidence/<run id>/
  run.json          what was asked for
  policy.json       the licence policy that was applied
  verdict.json      the decision and the reason for it
  diff.json         everything that changed between the two environments
  evidence.json     the same result in contract v1 form, with a hash for every file
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
| the version that resolved is not the one you named, on either side | Insufficient Evidence |
| the proposed version does not build | Reject |
| pip cannot install the proposed versions together | Reject (dependency conflict) |
| a new dependency conflict appears | Reject |
| a new known vulnerability appears | Reject |
| the upgrade adds a package the policy denies | Reject |
| a test passed before and fails, errors, is skipped or is missing after | Reject |
| the test suite ran before and cannot start after | Reject |
| the tests did not finish or collected nothing, and nothing else is wrong | Insufficient Evidence |
| none of the above | Accept |

Evidence that blocks always outranks tests that did not finish. A regression means a
test that passed before and does not pass after. A test that was already failing before
does not count, and neither does a test that never existed. That distinction is the
whole reason we build two environments instead of one.

## Benchmark

25 permissively licensed open source projects, 59 cases. The expected answer for every
case is committed before the tool is run on it; `benchmark/doc.md` explains how we
decide it and what the first run taught us. Results are in `benchmark/results.md`.

| method | accuracy | wrongly approved | wrongly rejected |
| --- | --- | --- | --- |
| UpgradeGuard | 100% | 0 | 0 |
| pip check only | 71% | 14 | 0 |
| pip-audit only | 56% | 23 | 0 |
| static file check only | 68% | 11 | 5 |

Three of the 59 cases are meant to end as Insufficient Evidence and they did. The first
run scored 88 percent and found real faults in our own tool; both runs are kept.

```
./.venv/bin/python -m upgradeguard fetch-repos
./.venv/bin/python -m upgradeguard benchmark --jobs 3 --test-timeout 420
```

The benchmark needs `python3.13` on the path and a good internet connection, and takes
about half an hour with three cases at a time.

## Tests

```
./.venv/bin/python -m pytest tests            # fast tests, a few seconds
./.venv/bin/python -m pytest tests --slow     # also builds real environments and runs Docker
./.venv/bin/python contracts/v1/check.py      # contract fixtures and digests
```

## Isolation

Each side gets its own virtual environment and its own copy of the project, both
created under `work/`. The two runs never share an interpreter, an installed package
or a working folder, and the tests never run against the original checkout. Every
command we run has a timeout. We do not import the project's code into our own
process at any point. A virtual environment is not a security boundary; use the
container runner for anything you did not write.

## What we are not building

No automatic code repair. No other languages. No support for every packaging tool
that exists. And no language model decides the verdict; it can only rephrase a
finished report.

## Layout

```
upgradeguard/     the tool
  spec.py         the request, name checks and the licence policy
  venvs.py        builds the clean environments
  metadata.py     reads installed package metadata
  graph.py        builds and compares dependency graphs
  checks/         conflicts, vulnerabilities, licences
  tests_run.py    runs pytest and reads the results
  verdict.py      the decision rules
  report.py       the evidence bundle and html report
  runner.py       ties one run together
  source.py       source manifests and archives
  snapshots.py    snapshots and comparisons
  contract.py     turns a run into contract v1 evidence
  worker.py       runs one contract request
  container.py    the Docker runner and the checks on its output
  baselines.py    the three tools we measure ourselves against
  metrics.py      benchmark metrics
  benchmark.py    the benchmark runner
  cli.py          the command line
contracts/v1/     shared JSON Schemas, fixtures and a checker
policies/         licence policies
examples/         small projects we test against
benchmark/        cases, repositories, results
web/              the website
tests/            the test suite
docs/             the planning presentation
```

## Team

Gurman Singh (1024030140), Madhur Tuteja (1024030145), Paryag (1024030125).
