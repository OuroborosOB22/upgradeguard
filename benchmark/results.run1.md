# Benchmark results

Cases: 59. Positive class is Reject. Ground truth was committed before these results.

## Verdicts against the baselines

| method | accuracy | precision | recall | false approvals | false rejections | inconclusive |
| --- | --- | --- | --- | --- | --- | --- |
| UpgradeGuard | 88.1% | 100.0% | 75.9% | 5 | 0 | 5 |
| pip check only | 71.2% | 88.2% | 51.7% | 14 | 0 | 0 |
| pip-audit only | 45.8% | n/a | 0.0% | 29 | 0 | 0 |
| static file check only | 67.8% | 72.0% | 62.1% | 11 | 5 | 0 |

## Detection by signal

| signal | cases | detected | detection rate |
| --- | --- | --- | --- |
| test-regression | 5 | 3 | 60.0% |
| dependency-conflict | 3 | 3 | 100.0% |
| vulnerability | 5 | 0 | 0.0% |
| licence-violation | 4 | 4 | 100.0% |
| build-failure | 14 | 14 | 100.0% |
| no-tests | 1 | 1 | 100.0% |

## Environment builds

- baseline environment built: 96.6%
- upgraded environment built when it should: 93.3%
- impossible builds correctly caught: 100.0%

## Execution time

- mean 42.7 s, median 12.74 s, longest 924.16 s, total 2519.02 s

## Every case

| case | expected | actual | ok | seconds |
| --- | --- | --- | --- | --- |
| demo-requests-safe | Accept | Accept | yes | 11.97 |
| demo-jinja2-removed-api | Reject | Reject | yes | 11.99 |
| demo-requests-missing-version | Reject | Reject | yes | 8.89 |
| demo-requests-strict-licence | Reject | Reject | yes | 9.48 |
| legacy-requests-drops-lgpl | Accept | Accept | yes | 10.0 |
| click-pytest-major-safe | Accept | Accept | yes | 11.09 |
| click-pytest-missing | Reject | Reject | yes | 7.32 |
| markupsafe-pytest-major-safe | Accept | Accept | yes | 11.11 |
| markupsafe-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 3.6 |
| itsdangerous-freezegun-patch-safe | Accept | Accept | yes | 11.35 |
| itsdangerous-dateutil-missing | Reject | Reject | yes | 7.12 |
| platformdirs-pytest-mock-patch-safe | Accept | Accept | yes | 14.21 |
| platformdirs-coverage-missing | Reject | Reject | yes | 9.05 |
| filelock-pytest-mock-patch-safe | Accept | Accept | yes | 32.69 |
| filelock-virtualenv-new-advisory | Reject | Accept | NO | 35.6 |
| filelock-pytest9-asyncio-conflict | Reject | Reject | yes | 19.54 |
| dotenv-sh-patch-safe | Accept | Accept | yes | 14.7 |
| dotenv-click-missing | Reject | Reject | yes | 8.91 |
| tenacity-pytest-minor-safe | Accept | Accept | yes | 17.2 |
| tenacity-tornado-new-advisory | Reject | Accept | NO | 16.91 |
| dateutil-six-minor-safe | Accept | Accept | yes | 18.5 |
| dateutil-hypothesis-strict-licence | Reject | Reject | yes | 18.77 |
| marshmallow-pytz-safe | Accept | Accept | yes | 12.23 |
| marshmallow-simplejson-missing | Reject | Reject | yes | 7.6 |
| records-sqlalchemy-14-regression | Reject | Reject | yes | 47.23 |
| records-pytest-minor-safe | Accept | Accept | yes | 78.51 |
| jinja-markupsafe-soft-unicode | Reject | Insufficient Evidence | NO | 11.29 |
| jinja-pytest-patch-safe | Accept | Accept | yes | 12.74 |
| flask-werkzeug-3-regression | Reject | Accept | NO | 14.78 |
| flask-click-patch-safe | Accept | Accept | yes | 14.84 |
| requests-urllib3-new-advisories | Reject | Accept | NO | 190.33 |
| requests-certifi-patch-safe | Accept | Accept | yes | 218.63 |
| requests-certifi-strict-licence | Reject | Reject | yes | 217.02 |
| httpx-idna-minor-safe | Accept | Accept | yes | 28.7 |
| httpx-cryptography-new-advisories | Reject | Insufficient Evidence | NO | 924.16 |
| httpx-h11-httpcore-conflict | Reject | Reject | yes | 18.13 |
| starlette-jinja2-patch-safe | Accept | Accept | yes | 23.06 |
| starlette-httpx-028-regression | Reject | Reject | yes | 22.99 |
| attrs-cloudpickle-minor-safe | Accept | Accept | yes | 40.28 |
| attrs-zope-missing | Reject | Reject | yes | 22.88 |
| rich-attrs-major-safe | Accept | Accept | yes | 19.8 |
| rich-mdurl-missing | Reject | Reject | yes | 11.51 |
| structlog-freezegun-patch-safe | Accept | Accept | yes | 19.82 |
| structlog-simplejson-missing | Reject | Reject | yes | 10.48 |
| anyio-psutil-minor-safe | Accept | Accept | yes | 63.2 |
| anyio-cryptography-new-advisories | Reject | Accept | NO | 61.68 |
| tomli-six-minor-safe | Accept | Accept | yes | 9.69 |
| tomli-baseline-missing | Insufficient Evidence | Insufficient Evidence | yes | 4.42 |
| tabulate-wcwidth-patch-safe | Accept | Accept | yes | 12.89 |
| tabulate-wcwidth-missing | Reject | Reject | yes | 7.88 |
| cachetools-pytest-minor-safe | Accept | Accept | yes | 10.11 |
| cachetools-pytest-missing | Reject | Reject | yes | 6.86 |
| humanize-freezegun-patch-safe | Accept | Accept | yes | 12.85 |
| humanize-dateutil-missing | Reject | Reject | yes | 8.16 |
| moreitertools-pytest-minor-safe | Accept | Accept | yes | 11.23 |
| moreitertools-no-tests-collected | Insufficient Evidence | Insufficient Evidence | yes | 8.5 |
| blinker-pytest-minor-safe | Accept | Accept | yes | 8.94 |
| blinker-pytest9-asyncio-conflict | Reject | Reject | yes | 6.38 |
| legacy-requests-rollback-adds-lgpl | Reject | Reject | yes | 9.22 |
