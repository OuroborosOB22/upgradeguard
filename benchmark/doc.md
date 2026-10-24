# How we decide the expected answer

The point of a benchmark is that we write down what should happen before we let the
tool answer. If we looked at the output first and then wrote the expected value, the
numbers would mean nothing.

## The process we follow for every case

1. Pick a repository and one direct dependency upgrade.
2. Read the upstream changelog, the release notes and the advisory databases by hand.
3. Write down the expected verdict and the expected signal in `cases.json`, together
   with a short `why` sentence explaining the reason in plain words.
4. Commit that file. The expected values are now fixed.
5. Only then run `upgradeguard benchmark`.
6. If the tool disagrees with us, we investigate. Sometimes the tool is wrong and we
   fix it. Sometimes we were wrong, and then we correct the case and say so in the
   commit message, so the change is visible in the history.

## The signals a case can expect

| signal | meaning |
| --- | --- |
| `none` | the upgrade is safe, we expect Accept |
| `test-regression` | a test that passed before must fail after |
| `dependency-conflict` | the resolved set must become internally inconsistent |
| `vulnerability` | a known advisory must appear that was not there before |
| `licence-violation` | the licence policy must be breached |
| `build-failure` | the upgraded environment must fail to install |

## Why the current five cases are what they are

- **demo-requests-safe.** A routine Requests upgrade. Nothing in our demo project
  uses a removed API, so this must pass. It is our check against false rejections.
- **demo-jinja2-removed-api.** Jinja2 3.1 removed the `jinja2.Markup` alias. This is
  a documented removal that broke a lot of real projects, so a project importing it
  must break. It is our check against false approvals.
- **demo-requests-missing-version.** There is no `requests 2.99.0`. The upgraded
  environment cannot be built, and the tool must say build failure rather than
  blaming the tests.
- **demo-requests-strict-licence.** `certifi` is published under MPL-2.0 and our
  strict policy does not allow MPL-2.0. This case runs in strict licence mode, where
  a policy breach in the resulting environment blocks the upgrade.
- **legacy-requests-drops-lgpl.** Requests 2.26 replaced `chardet`, which is LGPL,
  with `charset-normalizer`, which is MIT. The verdict must stay Accept and the
  evidence must show the LGPL package leaving the graph.

## Two levels of licence result

We separate the two on purpose.

- A violation the upgrade **introduces** blocks the verdict. The upgrade caused it.
- A violation that was **already there** is reported as a warning, because the
  upgrade did not cause it. Running with `--strict-licences` promotes it to blocking
  for teams that need the final environment to be clean no matter who caused it.

## Honest limitations right now

- Five cases is a starting point, not the benchmark. The plan is 20 to 25 repositories.
- The vulnerability service we query does not return a severity score, so we cannot
  yet grade a finding by how serious it is. Every new advisory is treated as blocking.
- Modern pip refuses to install an inconsistent set at all, so most conflicts show up
  as a build failure rather than as a `pip check` complaint. We kept the `pip check`
  stage because it still catches sets that were installed in separate steps.

## What the first run taught us

Run 1 (59 cases, ground truth committed first) got 52 verdicts right. The seven misses
were all useful, and each one was fixed in the tool or corrected in the case, in
separate commits:

| miss | what it really was | fix |
| --- | --- | --- |
| five vulnerability cases approved | pip-audit exits with a summary line after its JSON when it finds something, and we failed to parse that, so we silently fell back to the tiny offline list | read the first JSON value and ignore what follows |
| httpx cryptography case said Insufficient Evidence | the upgraded tests timed out, and the tool let that outrank a known new advisory | blocking evidence now outranks unfinished tests |
| jinja markupsafe case said Insufficient Evidence | after the upgrade pytest cannot even import the project, so no results exist | a suite that ran before and cannot start after is a rejection |
| flask werkzeug case approved | our expectation was wrong: Flask 2.2.5 had already dropped the url_quote import, Flask 2.2.3 still has it | the case now uses Flask 2.2.3 and the correction is written in its `why` |

Run 2 is the committed `results.json`. Run 1 is kept as `results.run1.json` so the
history stays visible. Nothing else in `cases.json` changed between the runs.

Two things the benchmark does not show: a 100 percent score on 59 cases we wrote
ourselves is not a claim about all projects, and the cases are mostly small, fast
libraries, not big applications.
