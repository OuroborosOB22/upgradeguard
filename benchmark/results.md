# Benchmark results

Cases: 59. Positive class is Reject. Ground truth was committed before these results.

Run details: jobs 3, machine MacBook arm64, 10 cores, 3 cases at a time, python python3.13 (uv), pip 25, run 2, test timeout 420, tool commit def76d7011394e08f0c794abf108feb4f69c7d32

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

- mean 27.9 s, median 12.98 s, longest 217.6 s, total 1645.95 s

## Every case

| case | expected | actual | ok | seconds |
| --- | --- | --- | --- | --- |
| demo-requests-safe | Accept | Accept | yes | 10.47 |
| demo-jinja2-removed-api | Reject | Reject | yes | 10.48 |
| demo-requests-missing-version | Reject | Reject | yes | 7.55 |
| demo-requests-strict-licence | Reject | Reject | yes | 9.71 |
| legacy-requests-drops-lgpl | Accept | Accept | yes | 9.13 |
| click-pytest-major-safe | Accept | Accept | yes | 11.66 |
| click-pytest-missing | Reject | Reject | yes | 7.86 |
| markupsafe-pytest-major-safe | Accept | Accept | yes | 11.52 |
| markupsafe-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 3.75 |
| itsdangerous-freezegun-patch-safe | Accept | Accept | yes | 12.59 |
| itsdangerous-dateutil-missing | Reject | Reject | yes | 7.88 |
| platformdirs-pytest-mock-patch-safe | Accept | Accept | yes | 16.32 |
| platformdirs-coverage-missing | Reject | Reject | yes | 9.94 |
| filelock-pytest-mock-patch-safe | Accept | Accept | yes | 36.2 |
| filelock-virtualenv-new-advisory | Reject | Reject | yes | 34.13 |
| filelock-pytest9-asyncio-conflict | Reject | Reject | yes | 20.22 |
| dotenv-sh-patch-safe | Accept | Accept | yes | 15.29 |
| dotenv-click-missing | Reject | Reject | yes | 9.06 |
| tenacity-pytest-minor-safe | Accept | Accept | yes | 17.3 |
| tenacity-tornado-new-advisory | Reject | Reject | yes | 16.57 |
| dateutil-six-minor-safe | Accept | Accept | yes | 20.19 |
| dateutil-hypothesis-strict-licence | Reject | Reject | yes | 18.75 |
| marshmallow-pytz-safe | Accept | Accept | yes | 12.98 |
| marshmallow-simplejson-missing | Reject | Reject | yes | 7.92 |
| records-sqlalchemy-14-regression | Reject | Reject | yes | 49.11 |
| records-pytest-minor-safe | Accept | Accept | yes | 79.31 |
| jinja-markupsafe-soft-unicode | Reject | Reject | yes | 12.87 |
| jinja-pytest-patch-safe | Accept | Accept | yes | 12.09 |
| flask-werkzeug-3-regression | Reject | Reject | yes | 13.63 |
| flask-click-patch-safe | Accept | Accept | yes | 14.69 |
| requests-urllib3-new-advisories | Reject | Reject | yes | 193.07 |
| requests-certifi-patch-safe | Accept | Accept | yes | 217.6 |
| requests-certifi-strict-licence | Reject | Reject | yes | 217.22 |
| httpx-idna-minor-safe | Accept | Accept | yes | 34.55 |
| httpx-cryptography-new-advisories | Reject | Reject | yes | 28.54 |
| httpx-h11-httpcore-conflict | Reject | Reject | yes | 17.45 |
| starlette-jinja2-patch-safe | Accept | Accept | yes | 23.83 |
| starlette-httpx-028-regression | Reject | Reject | yes | 22.02 |
| attrs-cloudpickle-minor-safe | Accept | Accept | yes | 41.67 |
| attrs-zope-missing | Reject | Reject | yes | 22.44 |
| rich-attrs-major-safe | Accept | Accept | yes | 20.33 |
| rich-mdurl-missing | Reject | Reject | yes | 11.4 |
| structlog-freezegun-patch-safe | Accept | Accept | yes | 18.28 |
| structlog-simplejson-missing | Reject | Reject | yes | 11.56 |
| anyio-psutil-minor-safe | Accept | Accept | yes | 61.76 |
| anyio-cryptography-new-advisories | Reject | Reject | yes | 60.93 |
| tomli-six-minor-safe | Accept | Accept | yes | 10.17 |
| tomli-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 4.37 |
| tabulate-wcwidth-patch-safe | Accept | Accept | yes | 13.58 |
| tabulate-wcwidth-missing | Reject | Reject | yes | 8.69 |
| cachetools-pytest-minor-safe | Accept | Accept | yes | 10.36 |
| cachetools-pytest-missing | Reject | Reject | yes | 6.7 |
| humanize-freezegun-patch-safe | Accept | Accept | yes | 14.48 |
| humanize-dateutil-missing | Reject | Reject | yes | 9.2 |
| moreitertools-pytest-minor-safe | Accept | Accept | yes | 11.93 |
| moreitertools-no-tests-collected | Insufficient Evidence | Insufficient Evidence | yes | 9.04 |
| blinker-pytest-minor-safe | Accept | Accept | yes | 9.83 |
| blinker-pytest9-asyncio-conflict | Reject | Reject | yes | 6.61 |
| legacy-requests-rollback-adds-lgpl | Reject | Reject | yes | 9.17 |
