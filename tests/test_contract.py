import json
import os
import sys

import pytest

from bundles import regression_bundle, side
from upgradeguard import contract, schemas

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contracts", "v1"))
import check as contract_check


def test_the_committed_fixtures_and_digests_are_consistent():
    assert contract_check.check_fixtures() == []
    assert contract_check.check_manifest() == []


def test_a_real_looking_bundle_maps_to_valid_evidence(tmp_path):
    evidence = contract.to_contract_evidence(regression_bundle(tmp_path), "2026-10-24T10:00:00Z")
    assert schemas.problems("evidence", evidence) == []


def test_verdict_and_findings_use_contract_names(tmp_path):
    evidence = contract.to_contract_evidence(regression_bundle(tmp_path), "2026-10-24T10:00:00Z")
    assert evidence["verdict"]["decision"] == "REJECT"
    codes = {item["code"]: item for item in evidence["verdict"]["findings"]}
    assert codes["test-regression"]["severity"] == "BLOCKING"
    assert codes["new-failing-tests"]["severity"] == "WARNING"


def test_finding_evidence_ids_point_at_real_artifacts_and_drop_unknown_paths(tmp_path):
    evidence = contract.to_contract_evidence(regression_bundle(tmp_path), "2026-10-24T10:00:00Z")
    known = {item["id"] for item in evidence["artifact_manifest"]}
    finding = [item for item in evidence["verdict"]["findings"] if item["code"] == "test-regression"][0]
    assert finding["evidence_ids"] == ["after-pytest.log"]
    assert set(finding["evidence_ids"]) <= known


def test_artifacts_are_relative_hashed_and_skip_unsafe_names(tmp_path):
    evidence = contract.to_contract_evidence(regression_bundle(tmp_path), "2026-10-24T10:00:00Z")
    paths = [item["path"] for item in evidence["artifact_manifest"]]
    assert "after/pytest.log" in paths and "weird name.txt" not in paths
    assert all(not path.startswith("/") and ".." not in path for path in paths)
    assert all(len(item["sha256"]) == 64 for item in evidence["artifact_manifest"])


def test_test_outcomes_and_stages_are_normalised(tmp_path):
    evidence = contract.to_contract_evidence(regression_bundle(tmp_path), "2026-10-24T10:00:00Z")
    after = evidence["after"]
    assert after["tests"]["stage"]["outcome"] == "FAIL"
    assert {item["outcome"] for item in after["tests"]["results"]} == {"ERROR", "SKIP"}
    assert evidence["before"]["tests"]["stage"]["outcome"] == "PASS"
    assert evidence["before"]["build"]["outcome"] == "NOT_RUN"


def test_regressions_and_missing_tests_are_listed_separately(tmp_path):
    diff = contract.to_contract_evidence(regression_bundle(tmp_path), "2026-10-24T10:00:00Z")["diff"]
    assert diff["tests"]["regressions"] == ["tests/test_a.py::test_one", "tests/test_b.py::test_gone"]
    assert diff["tests"]["missing_or_skipped"] == ["tests/test_b.py::test_gone"]
    assert diff["dependencies"]["changed"] == [{"name": "jinja2", "from": "3.0.3", "to": "3.1.6"}]


def test_a_failed_upgrade_build_still_validates(tmp_path):
    bundle = regression_bundle(tmp_path)
    bundle["after"] = side("3.1.6", build_ok=False)
    bundle["verdict"]["decision"] = "Reject"
    evidence = contract.to_contract_evidence(bundle, "2026-10-24T10:00:00Z")
    assert evidence["after"]["install"]["outcome"] == "FAIL"
    assert evidence["after"]["tests"]["stage"]["outcome"] == "NOT_RUN"
    assert schemas.problems("evidence", evidence) == []


def test_insufficient_evidence_maps_to_its_contract_name(tmp_path):
    bundle = regression_bundle(tmp_path)
    bundle["verdict"]["decision"] = "Insufficient Evidence"
    assert contract.to_contract_evidence(bundle, "2026-10-24T10:00:00Z")["verdict"]["decision"] == "INSUFFICIENT_EVIDENCE"


def test_request_block_hides_environment_values_and_names_the_change(tmp_path):
    request = contract.build_request(regression_bundle(tmp_path))
    assert request["environment_spec"]["env_var_names"] == ["SETUPTOOLS_SCM_PRETEND_VERSION"]
    assert "1.0" not in json.dumps(request["environment_spec"])
    assert request["change"] == {"ecosystem": "PYTHON", "package": "jinja2", "from_version": "3.0.3", "to_version": "3.1.6"}
    assert request["project_id"] == "demo_repo"
    assert request["profile_id"].startswith("pytest-") and request["profile_id"] != "pytest-default"


def test_slug_always_produces_a_valid_id():
    for text in ("A B", "..", "", "x", "UPPER_case-1", "a" * 200):
        value = contract.slug(text)
        assert 3 <= len(value) <= 64 and value[0].isalnum(), text


def test_long_artifact_paths_get_unique_short_ids():
    one = contract.artifact_id("a/" + "x" * 100 + "/one.log")
    two = contract.artifact_id("a/" + "x" * 100 + "/two.log")
    assert len(one) <= 64 and one != two


def test_validation_helper_raises_for_invalid_payloads():
    with pytest.raises(schemas.ContractError):
        schemas.require_valid("worker_result", {"schema_version": "1.0.0"})


def test_scanner_records_say_when_only_the_offline_list_was_used(tmp_path):
    bundle = regression_bundle(tmp_path)
    bundle["after"]["vulnerabilities"] = {"source": "bundled-advisories", "available": False, "findings": []}
    evidence = contract.to_contract_evidence(bundle, "2026-10-24T10:00:00Z")
    scanner = evidence["after"]["scanner_results"][0]
    assert scanner["scanner"] == "bundled-advisories" and scanner["available"] is False
    assert "online vulnerability scan (after)" in evidence["coverage"]["unavailable"]
