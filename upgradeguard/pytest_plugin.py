import os
import platform
import shutil
import tempfile
import warnings

STORE_VARIABLE = "UPGRADEGUARD_SNAPSHOT_DIR"
ACTIVE_VARIABLE = "UPGRADEGUARD_ACTIVE"

OUTCOMES = {"passed": "passed", "failed": "failed", "skipped": "skipped"}


def enabled():
    return bool(os.environ.get(STORE_VARIABLE)) and not os.environ.get(ACTIVE_VARIABLE)


class Recorder:
    def __init__(self, config):
        self.config = config
        self.results = {}

    def pytest_runtest_logreport(self, report):
        status = OUTCOMES.get(report.outcome, "error")
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            if report.when == "setup" and report.outcome == "failed":
                status = "error"
            self.results[report.nodeid] = {"status": status, "message": "", "time": str(report.duration)}
        elif report.when == "teardown" and report.outcome == "failed":
            self.results[report.nodeid] = {"status": "error", "message": "", "time": str(report.duration)}

    def pytest_sessionfinish(self, session, exitstatus):
        try:
            self.record(session, int(exitstatus))
        except Exception as failure:
            warnings.warn("upgradeguard could not record a snapshot: %s" % failure)

    def record(self, session, exitstatus):
        from .contract import environment_block, profile_id, slug
        from .snapshots import eligibility_for, project_dir, store_snapshot
        from .source import build_manifest, describe_source
        from .tests_run import count_statuses

        root = str(self.config.rootpath)
        store = os.environ[STORE_VARIABLE]
        project = slug(os.path.basename(root.rstrip("/")))
        profile = profile_id(list(self.config.invocation_params.args))
        source = describe_source(root)
        manifest = build_manifest(root)
        counts = count_statuses(self.results)
        tests = {"ran": bool(self.results), "returncode": exitstatus, "timed_out": False, "counts": counts, "results": self.results}
        dependencies = installed_dependencies()
        eligibility = eligibility_for({"ok": True}, tests, True)
        environment = environment_block(platform.python_version(), True)
        os.makedirs(project_dir(store, project), exist_ok=True)
        staging = tempfile.mkdtemp(prefix=".staging-", dir=project_dir(store, project))
        try:
            store_snapshot(store, project, profile, source, manifest, root, environment, dependencies, tests, True, eligibility, staging)
        finally:
            shutil.rmtree(staging, ignore_errors=True)


def installed_dependencies():
    from importlib.metadata import distributions
    seen = {}
    for dist in distributions():
        name = (dist.metadata["Name"] or "").lower().replace("_", "-").replace(".", "-")
        if name and name not in ("pip", "setuptools", "wheel"):
            seen[name] = dist.version
    return [{"name": name, "version": version} for name, version in sorted(seen.items())]


def pytest_configure(config):
    if enabled() and not config.pluginmanager.has_plugin("upgradeguard-recorder"):
        config.pluginmanager.register(Recorder(config), "upgradeguard-recorder")
