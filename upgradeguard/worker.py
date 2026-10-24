import json
import os
import shutil
import tempfile

from . import schemas
from .contract import utc_now
from .runner import run_upgrade_check
from .snapshots import capture_snapshot
from .source import describe_source
from .spec import UpgradeSpec, load_policy, validate_spec
from .util import read_json, write_json
from .verdict import ACCEPT, INSUFFICIENT, REJECT

VERDICTS = {ACCEPT: "ACCEPT", REJECT: "REJECT", INSUFFICIENT: "INSUFFICIENT_EVIDENCE"}
PYTHON_OPERATIONS = ("REHEARSE_UPGRADE", "REHEARSE_RECOVERY")


def result_record(started, run_id=None, operation=None, state="FAILED", verdict=None, evidence_path=None, error=None):
    return {
        "schema_version": schemas.load_schema("worker_result")["properties"]["schema_version"]["const"],
        "run_id": run_id, "operation": operation, "job_state": state, "verdict": verdict,
        "evidence_path": evidence_path, "error": error[:1000] if error else None,
        "started_at": started, "finished_at": utc_now(),
    }


def check_source_matches(request, source_dir):
    actual = describe_source(source_dir)["manifest_sha256"]
    if actual != request["source"]["manifest_sha256"]:
        raise ValueError("the mounted source does not match the manifest in the request")


def run_python_job(request, source_dir, out_dir, work_dir, python_bin, offline, progress, options):
    change = request["change"]
    spec = UpgradeSpec(repo_path=source_dir, package=change["package"], from_version=change["from_version"],
                       to_version=change["to_version"], python_bin=python_bin, run_id=request["run_id"],
                       requirements_file=options.get("requirements", "requirements.txt"),
                       install_project=options.get("install_project", False), pytest_args=options.get("pytest_args", []))
    validate_spec(spec)
    policy_path = options.get("policy", "")
    bundle = run_upgrade_check(
        spec, load_policy(policy_path if policy_path and os.path.isfile(policy_path) else ""),
        evidence_root=out_dir, work_root=work_dir, allow_network=not offline, progress=progress,
        strict_licences=options.get("strict_licences", False),
        operation=request["operation"], execution_provider=request["execution_provider"],
        image_digest=request["environment_spec"].get("image_digest"))
    return VERDICTS[bundle["verdict"]["decision"]], "%s/evidence.json" % request["run_id"]


def run_snapshot_job(request, source_dir, out_dir, python_bin, offline, progress):
    record, _ = capture_snapshot(source_dir, os.path.join(out_dir, "snapshots"), python_bin=python_bin, allow_network=not offline, progress=progress)
    return None, "snapshots/%s/%s/snapshot.json" % (record["project_id"], record["snapshot_id"])


def publish(out_dir, publish_dir):
    os.makedirs(publish_dir, exist_ok=True)
    for name in os.listdir(publish_dir):
        full = os.path.join(publish_dir, name)
        shutil.rmtree(full) if os.path.isdir(full) and not os.path.islink(full) else os.remove(full)
    for current, folders, names in os.walk(out_dir):
        relative = os.path.relpath(current, out_dir)
        target = publish_dir if relative == "." else os.path.join(publish_dir, relative)
        folders[:] = [name for name in folders if not os.path.islink(os.path.join(current, name))]
        os.makedirs(target, exist_ok=True)
        for name in names:
            source = os.path.join(current, name)
            if os.path.isfile(source) and not os.path.islink(source):
                shutil.copyfile(source, os.path.join(target, name))


def run_worker(request_path, source_dir, out_dir, python_bin="python3", offline=False, work_dir=None, progress=None, options=None, publish_dir=None):
    started = utc_now()
    os.makedirs(out_dir, exist_ok=True)
    request = None
    own_work = work_dir is None
    work_dir = work_dir or tempfile.mkdtemp(prefix="ug-worker-")
    try:
        request = schemas.require_valid("request", read_json(request_path))
        check_source_matches(request, source_dir)
        if request["operation"] in PYTHON_OPERATIONS:
            verdict, evidence_path = run_python_job(request, source_dir, out_dir, work_dir, python_bin, offline, progress, options or {})
        elif request["operation"] == "SNAPSHOT":
            verdict, evidence_path = run_snapshot_job(request, source_dir, out_dir, python_bin, offline, progress)
        else:
            raise ValueError("%s is available through the compare command, not the worker" % request["operation"])
        result = result_record(started, request["run_id"], request["operation"], "SUCCEEDED", verdict, evidence_path)
    except Exception as failure:
        result = result_record(started, request["run_id"] if request else None, request["operation"] if request else None,
                               "FAILED", error=str(failure))
    finally:
        if own_work:
            shutil.rmtree(work_dir, ignore_errors=True)
    schemas.require_valid("worker_result", result)
    write_json(os.path.join(out_dir, "result.json"), result)
    if publish_dir:
        publish(out_dir, publish_dir)
    return result
