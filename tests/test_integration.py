import json
import os
import subprocess
import sys

import pytest

from upgradeguard import schemas
from upgradeguard.contract import file_sha256, request_from_parts
from upgradeguard.source import build_manifest, describe_source

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "demo_repo")

pytestmark = pytest.mark.slow


def cli(*arguments, cwd=ROOT, env=None):
    merged = dict(os.environ)
    merged.update(env or {})
    return subprocess.run([sys.executable, "-m", "upgradeguard", *arguments], cwd=cwd, capture_output=True, text=True, env=merged)


def demo_hash():
    return build_manifest(DEMO)["manifest_sha256"]


@pytest.mark.parametrize("package,old,new,code,decision", [
    ("requests", "2.28.2", "2.32.5", 0, "ACCEPT"),
    ("jinja2", "3.0.3", "3.1.6", 1, "REJECT"),
    ("requests", "2.28.2", "2.99.0", 1, "REJECT"),
])
def test_json_output_is_one_valid_document_and_the_checkout_is_untouched(tmp_path, package, old, new, code, decision):
    before = demo_hash()
    done = cli("run", "--repo", DEMO, "--package", package, "--from", old, "--to", new, "--json",
               "--evidence", str(tmp_path / "e"), "--work", str(tmp_path / "w"))
    assert done.returncode == code, done.stderr[-500:]
    evidence = json.loads(done.stdout)
    assert schemas.problems("evidence", evidence) == []
    assert evidence["verdict"]["decision"] == decision
    assert "building before environment" in done.stderr
    assert demo_hash() == before


def test_json_evidence_links_the_reason_to_real_files(tmp_path):
    done = cli("run", "--repo", DEMO, "--package", "jinja2", "--from", "3.0.3", "--to", "3.1.6", "--json",
               "--evidence", str(tmp_path / "e"), "--work", str(tmp_path / "w"))
    evidence = json.loads(done.stdout)
    run_dir = next((tmp_path / "e").iterdir())
    finding = [item for item in evidence["verdict"]["findings"] if item["code"] == "test-regression"][0]
    assert finding["evidence_ids"]
    by_id = {item["id"]: item for item in evidence["artifact_manifest"]}
    for identifier in finding["evidence_ids"]:
        artifact = by_id[identifier]
        assert file_sha256(str(run_dir / artifact["path"])) == artifact["sha256"]
    assert len(evidence["diff"]["tests"]["regressions"]) == 5


def test_a_failure_in_json_mode_is_still_one_valid_document(tmp_path):
    done = cli("run", "--repo", str(tmp_path / "missing"), "--package", "six", "--from", "1", "--to", "2", "--json",
               "--evidence", str(tmp_path / "e"), "--work", str(tmp_path / "w"))
    assert done.returncode == 3
    result = json.loads(done.stdout)
    assert schemas.problems("worker_result", result) == []
    assert result["job_state"] == "FAILED"


def make_project(tmp_path, test_body="def test_ok():\n    assert True\n"):
    project = tmp_path / "proj"
    project.mkdir(exist_ok=True)
    (project / "requirements.txt").write_text("six==1.16.0\n")
    (project / "app.py").write_text("VALUE = 1\n")
    (project / "test_app.py").write_text(test_body)
    return project


def snapshot(project, store, *extra):
    done = cli("snapshot-run", "--repo", str(project), "--store", str(store), "--json", "--quiet", *extra)
    return done, json.loads(done.stdout)


def test_snapshot_compare_and_recovery_flow(tmp_path):
    project = make_project(tmp_path)
    store = tmp_path / "store"
    done, first = snapshot(project, store)
    assert done.returncode == 0 and first["eligibility"] == "PASSING"
    assert schemas.problems("snapshot", first) == []
    assert [item["id"] for item in first["tests"]["results"]] == ["test_app::test_ok"]

    _, again = snapshot(project, store)
    assert again["snapshot_id"] == first["snapshot_id"]
    assert len(json.loads((store / "proj" / "index.json").read_text())) == 1

    (project / "app.py").write_text("VALUE = 2\n")
    (project / "test_app.py").write_text("def test_ok():\n    assert False\n")
    _, broken = snapshot(project, store)
    assert broken["eligibility"] == "STARTING_ONLY" and broken["snapshot_id"] != first["snapshot_id"]

    compared = cli("compare", "--store", str(store), "--project", "proj", "--old", first["snapshot_id"], "--new", broken["snapshot_id"], "--json")
    assert compared.returncode == 0
    comparison = json.loads(compared.stdout)
    assert schemas.problems("comparison", comparison) == []
    assert comparison["changes"]["tests"]["newly_failing"] == ["test_app::test_ok"]
    assert comparison["changes"]["code"]["changed"] == ["app.py", "test_app.py"]
    assert any("lead, not proof" in text for text in comparison["warnings"])

    (project / "requirements.txt").write_text("six==1.17.0\n")
    (project / "test_app.py").write_text("def test_ok():\n    assert True\n")
    before = build_manifest(str(project))["manifest_sha256"]
    recovered = cli("recover", "--repo", str(project), "--store", str(store), "--project", "proj", "--snapshot", first["snapshot_id"],
                    "--package", "six", "--evidence", str(tmp_path / "e"), "--work", str(tmp_path / "w"), "--json")
    assert recovered.returncode == 0, recovered.stderr[-400:]
    evidence = json.loads(recovered.stdout)
    assert evidence["request"]["operation"] == "REHEARSE_RECOVERY"
    assert evidence["request"]["change"]["from_version"] == "1.17.0" and evidence["request"]["change"]["to_version"] == "1.16.0"
    assert build_manifest(str(project))["manifest_sha256"] == before


def test_unverified_and_unfinished_snapshots_are_labelled(tmp_path):
    project = make_project(tmp_path)
    _, starting = snapshot(project, tmp_path / "store", "--no-verify")
    assert starting["eligibility"] == "STARTING_ONLY" and starting["tests"]["verified"] is False
    (project / "test_app.py").write_text("def test_ok():\n    assert True\n")
    empty, none_collected = snapshot(project, tmp_path / "store2", "--pytest-arg=-k", "--pytest-arg=nothing_matches")
    assert none_collected["eligibility"] == "INCONCLUSIVE" and empty.returncode == 2
    (project / "requirements.txt").write_text("six==99.0.0\n")
    broken, build_failed = snapshot(project, tmp_path / "store3")
    assert build_failed["eligibility"] == "INCONCLUSIVE" and broken.returncode == 2


def test_snapshots_never_store_secret_files(tmp_path):
    project = make_project(tmp_path)
    (project / ".env").write_text("TOKEN=abc123")
    (project / "server.pem").write_text("-----BEGIN PRIVATE KEY-----")
    _, record = snapshot(project, tmp_path / "store")
    stored = tmp_path / "store" / "proj" / record["snapshot_id"]
    archive_text = subprocess.run(["tar", "-tzf", str(stored / "source.tar.gz")], capture_output=True, text=True).stdout
    assert ".env" not in archive_text and "server.pem" not in archive_text and "app.py" in archive_text
    assert "abc123" not in (stored / "manifest.json").read_text()


def test_worker_runs_a_contract_request_end_to_end(tmp_path):
    project = make_project(tmp_path)
    (project / "requirements.txt").write_text("six==1.16.0\n")
    spec = {"package": "six", "from_version": "1.16.0", "to_version": "1.17.0", "pytest_args": [], "build_env": {}}
    request = request_from_parts("run-worker-e2e", str(project), describe_source(str(project)), spec, "default", "3.12", True)
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))
    done = cli("worker", "--request", str(request_path), "--source", str(project), "--out", str(tmp_path / "out"))
    assert done.returncode == 0, done.stderr[-500:]
    result = json.loads((tmp_path / "out" / "result.json").read_text())
    assert schemas.problems("worker_result", result) == []
    assert result["job_state"] == "SUCCEEDED" and result["verdict"] == "ACCEPT"
    evidence = json.loads((tmp_path / "out" / result["evidence_path"]).read_text())
    assert schemas.problems("evidence", evidence) == []
    for item in evidence["artifact_manifest"]:
        assert file_sha256(str(tmp_path / "out" / "run-worker-e2e" / item["path"])) == item["sha256"]
