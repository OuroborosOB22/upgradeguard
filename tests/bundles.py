import os

from upgradeguard.spec import UpgradeSpec


def side(version, passed=True, build_ok=True):
    results = {"tests/test_a.py::test_one": {"status": "passed" if passed else "error", "message": ""},
               "tests/test_a.py::test_two": {"status": "skipped", "message": ""}}
    return {
        "build": {"ok": build_ok, "failure_stage": "" if build_ok else "dependency-install", "install_returncode": 0 if build_ok else 1,
                  "duration": 4.2, "python_version": "3.12.4"},
        "graph": {"nodes": {"jinja2": {"version": version}, "markupsafe": {"version": "2.1.5"}}},
        "conflicts": {"problems": []},
        "vulnerabilities": {"source": "pip-audit", "available": True, "findings": []},
        "licenses": {"violations": []},
        "tests": {"ran": build_ok, "timed_out": False, "returncode": 0 if passed else 1, "duration": 0.5, "results": results if build_ok else {},
                  "counts": {}},
    }


def regression_bundle(tmp_path):
    evidence = tmp_path / "evidence" / "run-one"
    for relative in ("before/install.log", "after/install.log", "after/pytest.log", "after/junit.xml", "diff.json", "before/freeze.txt"):
        path = evidence / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content of %s" % relative)
    (evidence / "weird name.txt").write_text("not portable")
    spec = UpgradeSpec(repo_path=str(tmp_path / "Demo_Repo"), package="Jinja2", from_version="3.0.3", to_version="3.1.6",
                       pytest_args=["-W", "ignore"], build_env={"SETUPTOOLS_SCM_PRETEND_VERSION": "1.0"}).to_dict()
    return {
        "run_id": "20261024-120000-jinja2-3_0_3-to-3_1_6",
        "spec": spec,
        "source": {"commit": None, "dirty": False, "manifest_sha256": "a" * 64, "snapshot_id": "snap-aaaaaaaaaaaa", "exclusions": [".git"]},
        "policy": {"name": "default-permissive"},
        "options": {"strict_licences": False, "allow_network": True},
        "before": side("3.0.3"),
        "after": side("3.1.6", passed=False),
        "diff": {
            "graph": {"added": [{"name": "newdep"}], "removed": [], "changed": [{"name": "jinja2", "from_version": "3.0.3", "to_version": "3.1.6"}]},
            "tests": {"regressions": [{"test": "tests/test_a.py::test_one", "after": "error"},
                                      {"test": "tests/test_b.py::test_gone", "after": "not collected"}],
                      "new_failing_tests": [{"test": "tests/test_c.py::test_new"}]},
        },
        "verdict": {"decision": "Reject", "headline": "Reject: x",
                    "reasons": [{"code": "test-regression", "message": "2 test(s) passed before and fail after", "evidence": ["after/pytest.log", "missing/file.log"], "severity": "blocking"}],
                    "notes": [{"code": "new-failing-tests", "message": "1 new failing", "evidence": ["after/junit.xml"], "severity": "warning"}]},
        "evidence_dir": str(evidence),
    }
