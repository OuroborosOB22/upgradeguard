# Benchmark results

Cases: 59. Positive class is Reject. Ground truth was committed before these results.

Run details: jobs 3, machine MacBook arm64, 10 cores, 3 cases at a time, python python3.13 (uv), pip 25, run 3, test timeout 420, timing caveat other builds were running on the same machine so times are higher than in run 2, tool commit af9f525101ed658fba4a15864282a94fbcb67727

## Verdicts against the baselines

| method | accuracy | precision | recall | false approvals | false rejections | inconclusive |
| --- | --- | --- | --- | --- | --- | --- |
| UpgradeGuard | 100.0% | 100.0% | 100.0% | 0 | 0 | 3 |
| pip check only | 71.2% | 88.2% | 51.7% | 14 | 0 | 0 |
| pip-audit only | 55.9% | 100.0% | 20.7% | 23 | 0 | 0 |
| static file check only | 67.8% | 72.0% | 62.1% | 11 | 5 | 0 |

## Detection by signal

| signal | cases | detected | detection rate |
| --- | --- | --- | --- |
| test-regression | 5 | 5 | 100.0% |
| dependency-conflict | 3 | 3 | 100.0% |
| vulnerability | 5 | 5 | 100.0% |
| licence-violation | 4 | 4 | 100.0% |
| build-failure | 14 | 14 | 100.0% |
| no-tests | 1 | 1 | 100.0% |

## Environment builds

- baseline environment built: 96.6%
- upgraded environment built when it should: 100.0%
- impossible builds correctly caught: 100.0%

## Execution time

- mean 36.65 s, median 13.82 s, longest 446.87 s, total 2162.64 s

## Every case

| case | expected | actual | ok | seconds |
| --- | --- | --- | --- | --- |
| demo-requests-safe | Accept | Accept | yes | 11.25 |
| demo-jinja2-removed-api | Reject | Reject | yes | 11.27 |
| demo-requests-missing-version | Reject | Reject | yes | 8.34 |
| demo-requests-strict-licence | Reject | Reject | yes | 10.16 |
| legacy-requests-drops-lgpl | Accept | Accept | yes | 11.4 |
| click-pytest-major-safe | Accept | Accept | yes | 16.56 |
| click-pytest-missing | Reject | Reject | yes | 8.45 |
| markupsafe-pytest-major-safe | Accept | Accept | yes | 12.5 |
| markupsafe-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 4.02 |
| itsdangerous-freezegun-patch-safe | Accept | Accept | yes | 13.82 |
| itsdangerous-dateutil-missing | Reject | Reject | yes | 7.97 |
| platformdirs-pytest-mock-patch-safe | Accept | Accept | yes | 17.03 |
| platformdirs-coverage-missing | Reject | Reject | yes | 9.91 |
| filelock-pytest-mock-patch-safe | Accept | Accept | yes | 42.49 |
| filelock-virtualenv-new-advisory | Reject | Reject | yes | 39.25 |
| filelock-pytest9-asyncio-conflict | Reject | Reject | yes | 22.96 |
| dotenv-sh-patch-safe | Accept | Accept | yes | 15.56 |
| dotenv-click-missing | Reject | Reject | yes | 9.2 |
| tenacity-pytest-minor-safe | Accept | Accept | yes | 18.24 |
| tenacity-tornado-new-advisory | Reject | Reject | yes | 17.76 |
| dateutil-six-minor-safe | Accept | Accept | yes | 21.5 |
| dateutil-hypothesis-strict-licence | Reject | Reject | yes | 19.53 |
| marshmallow-pytz-safe | Accept | Accept | yes | 13.57 |
| marshmallow-simplejson-missing | Reject | Reject | yes | 8.44 |
| records-sqlalchemy-14-regression | Reject | Reject | yes | 48.32 |
| records-pytest-minor-safe | Accept | Accept | yes | 77.5 |
| jinja-markupsafe-soft-unicode | Reject | Reject | yes | 13.44 |
| jinja-pytest-patch-safe | Accept | Accept | yes | 12.85 |
| flask-werkzeug-3-regression | Reject | Reject | yes | 16.03 |
| flask-click-patch-safe | Accept | Accept | yes | 15.24 |
| requests-urllib3-new-advisories | Reject | Reject | yes | 194.53 |
| requests-certifi-patch-safe | Accept | Accept | yes | 220.71 |
| requests-certifi-strict-licence | Reject | Reject | yes | 219.84 |
| httpx-idna-minor-safe | Accept | Accept | yes | 51.34 |
| httpx-cryptography-new-advisories | Reject | Reject | yes | 446.87 |
| httpx-h11-httpcore-conflict | Reject | Reject | yes | 21.54 |
| starlette-jinja2-patch-safe | Accept | Accept | yes | 29.74 |
| starlette-httpx-028-regression | Reject | Reject | yes | 28.61 |
| attrs-cloudpickle-minor-safe | Accept | Accept | yes | 45.47 |
| attrs-zope-missing | Reject | Reject | yes | 23.65 |
| rich-attrs-major-safe | Accept | Accept | yes | 21.36 |
| rich-mdurl-missing | Reject | Reject | yes | 13.13 |
| structlog-freezegun-patch-safe | Accept | Accept | yes | 20.77 |
| structlog-simplejson-missing | Reject | Reject | yes | 12.5 |
| anyio-psutil-minor-safe | Accept | Accept | yes | 65.66 |
| anyio-cryptography-new-advisories | Reject | Reject | yes | 64.09 |
| tomli-six-minor-safe | Accept | Accept | yes | 11.26 |
| tomli-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 4.38 |
| tabulate-wcwidth-patch-safe | Accept | Accept | yes | 13.6 |
| tabulate-wcwidth-missing | Reject | Reject | yes | 8.44 |
| cachetools-pytest-minor-safe | Accept | Accept | yes | 10.82 |
| cachetools-pytest-missing | Reject | Reject | yes | 7.05 |
| humanize-freezegun-patch-safe | Accept | Accept | yes | 14.15 |
| humanize-dateutil-missing | Reject | Reject | yes | 9.24 |
| moreitertools-pytest-minor-safe | Accept | Accept | yes | 12.62 |
| moreitertools-no-tests-collected | Insufficient Evidence | Insufficient Evidence | yes | 8.85 |
| blinker-pytest-minor-safe | Accept | Accept | yes | 10.07 |
| blinker-pytest9-asyncio-conflict | Reject | Reject | yes | 7.12 |
| legacy-requests-rollback-adds-lgpl | Reject | Reject | yes | 10.67 |
