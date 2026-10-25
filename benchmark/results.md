# Benchmark results

Cases: 59. Positive class is Reject. Ground truth was committed before these results.

Run details: jobs 3, test timeout 420

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

- mean 36.44 s, median 14.88 s, longest 434.4 s, total 2150.21 s

## Every case

| case | expected | actual | ok | seconds |
| --- | --- | --- | --- | --- |
| demo-requests-safe | Accept | Accept | yes | 15.6 |
| demo-jinja2-removed-api | Reject | Reject | yes | 14.88 |
| demo-requests-missing-version | Reject | Reject | yes | 10.91 |
| demo-requests-strict-licence | Reject | Reject | yes | 12.14 |
| legacy-requests-drops-lgpl | Accept | Accept | yes | 12.0 |
| click-pytest-major-safe | Accept | Accept | yes | 14.16 |
| click-pytest-missing | Reject | Reject | yes | 8.37 |
| markupsafe-pytest-major-safe | Accept | Accept | yes | 12.44 |
| markupsafe-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 4.07 |
| itsdangerous-freezegun-patch-safe | Accept | Accept | yes | 13.31 |
| itsdangerous-dateutil-missing | Reject | Reject | yes | 7.75 |
| platformdirs-pytest-mock-patch-safe | Accept | Accept | yes | 16.91 |
| platformdirs-coverage-missing | Reject | Reject | yes | 9.96 |
| filelock-pytest-mock-patch-safe | Accept | Accept | yes | 39.55 |
| filelock-virtualenv-new-advisory | Reject | Reject | yes | 36.47 |
| filelock-pytest9-asyncio-conflict | Reject | Reject | yes | 21.53 |
| dotenv-sh-patch-safe | Accept | Accept | yes | 17.35 |
| dotenv-click-missing | Reject | Reject | yes | 10.95 |
| tenacity-pytest-minor-safe | Accept | Accept | yes | 19.76 |
| tenacity-tornado-new-advisory | Reject | Reject | yes | 17.78 |
| dateutil-six-minor-safe | Accept | Accept | yes | 21.58 |
| dateutil-hypothesis-strict-licence | Reject | Reject | yes | 20.45 |
| marshmallow-pytz-safe | Accept | Accept | yes | 13.37 |
| marshmallow-simplejson-missing | Reject | Reject | yes | 8.41 |
| records-sqlalchemy-14-regression | Reject | Reject | yes | 50.69 |
| records-pytest-minor-safe | Accept | Accept | yes | 81.54 |
| jinja-markupsafe-soft-unicode | Reject | Reject | yes | 14.65 |
| jinja-pytest-patch-safe | Accept | Accept | yes | 12.74 |
| flask-werkzeug-3-regression | Reject | Reject | yes | 16.11 |
| flask-click-patch-safe | Accept | Accept | yes | 16.14 |
| requests-urllib3-new-advisories | Reject | Reject | yes | 193.97 |
| requests-certifi-patch-safe | Accept | Accept | yes | 219.63 |
| requests-certifi-strict-licence | Reject | Reject | yes | 221.12 |
| httpx-idna-minor-safe | Accept | Accept | yes | 35.1 |
| httpx-cryptography-new-advisories | Reject | Reject | yes | 31.56 |
| httpx-h11-httpcore-conflict | Reject | Reject | yes | 434.4 |
| starlette-jinja2-patch-safe | Accept | Accept | yes | 24.77 |
| starlette-httpx-028-regression | Reject | Reject | yes | 24.14 |
| attrs-cloudpickle-minor-safe | Accept | Accept | yes | 45.48 |
| attrs-zope-missing | Reject | Reject | yes | 24.54 |
| rich-attrs-major-safe | Accept | Accept | yes | 21.41 |
| rich-mdurl-missing | Reject | Reject | yes | 12.48 |
| structlog-freezegun-patch-safe | Accept | Accept | yes | 19.5 |
| structlog-simplejson-missing | Reject | Reject | yes | 11.6 |
| anyio-psutil-minor-safe | Accept | Accept | yes | 65.51 |
| anyio-cryptography-new-advisories | Reject | Reject | yes | 62.61 |
| tomli-six-minor-safe | Accept | Accept | yes | 10.96 |
| tomli-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 4.52 |
| tabulate-wcwidth-patch-safe | Accept | Accept | yes | 14.17 |
| tabulate-wcwidth-missing | Reject | Reject | yes | 8.65 |
| cachetools-pytest-minor-safe | Accept | Accept | yes | 11.46 |
| cachetools-pytest-missing | Reject | Reject | yes | 7.35 |
| humanize-freezegun-patch-safe | Accept | Accept | yes | 15.13 |
| humanize-dateutil-missing | Reject | Reject | yes | 8.91 |
| moreitertools-pytest-minor-safe | Accept | Accept | yes | 12.66 |
| moreitertools-no-tests-collected | Insufficient Evidence | Insufficient Evidence | yes | 9.3 |
| blinker-pytest-minor-safe | Accept | Accept | yes | 10.18 |
| blinker-pytest9-asyncio-conflict | Reject | Reject | yes | 7.16 |
| legacy-requests-rollback-adds-lgpl | Reject | Reject | yes | 10.37 |
