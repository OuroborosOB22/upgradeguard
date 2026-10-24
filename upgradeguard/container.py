import json
import os
import shutil
import tempfile

from . import schemas
from .contract import file_sha256, request_from_parts
from .source import describe_source
from .spec import validate_python_name
from .util import run_command, read_json

DEFAULT_IMAGE = "upgradeguard-runner:local"
MAX_OUTPUT_BYTES = 500 * 1024 * 1024
MEMORY = "4g"
CPUS = "2"
PIDS = "512"
WORK_SIZE = "4g"


def image_digest(image):
    inspected = run_command(["docker", "image", "inspect", "--format", "{{.Id}}", image], timeout=60)
    return inspected["output"].strip() if inspected["returncode"] == 0 else ""


def docker_available():
    return shutil.which("docker") is not None and run_command(["docker", "info"], timeout=60)["returncode"] == 0


def docker_command(image, repo_path, request_dir, out_dir, digest, user, offline=False, name=None, extra=None):
    command = ["docker", "run", "--rm"]
    if name:
        command += ["--name", name]
    command += [
        "--user", user, "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--memory", MEMORY, "--cpus", CPUS, "--pids-limit", PIDS,
        "--tmpfs", "/work:rw,exec,nosuid,size=%s" % WORK_SIZE, "--tmpfs", "/tmp:rw,nosuid,size=512m",
        "-v", "%s:/input/repo:ro" % repo_path, "-v", "%s:/input/request:ro" % request_dir, "-v", "%s:/output:rw" % out_dir,
        "-e", "HOME=/work/home", "-e", "UPGRADEGUARD_IMAGE_DIGEST=%s" % digest,
        image, "worker", "--request", "/input/request/request.json", "--source", "/input/repo", "--out", "/work/out", "--publish", "/output", "--work", "/work/jobs",
    ]
    if offline:
        command.append("--offline")
    return command + list(extra or [])


class UntrustedOutput(Exception):
    pass


def verify_output(directory, request):
    total = 0
    for current, folders, names in os.walk(directory):
        for name in folders + names:
            full = os.path.join(current, name)
            if os.path.islink(full):
                raise UntrustedOutput("the container left a link at %s" % os.path.relpath(full, directory))
        for name in names:
            full = os.path.join(current, name)
            if not os.path.isfile(full):
                raise UntrustedOutput("the container left a file that is not a regular file")
            total += os.path.getsize(full)
    if total > MAX_OUTPUT_BYTES:
        raise UntrustedOutput("the container output is larger than %d bytes" % MAX_OUTPUT_BYTES)
    evidence = read_json(os.path.join(directory, "evidence.json"))
    schemas.require_valid("evidence", evidence)
    if evidence["request"]["run_id"] != request["run_id"] or evidence["request"]["source"]["manifest_sha256"] != request["source"]["manifest_sha256"]:
        raise UntrustedOutput("the evidence does not belong to the job that was requested")
    listed = {item["path"]: item["sha256"] for item in evidence["artifact_manifest"]}
    present = {os.path.relpath(os.path.join(current, name), directory).replace(os.sep, "/")
               for current, _, names in os.walk(directory) for name in names} - {"evidence.json"}
    if present != set(listed):
        raise UntrustedOutput("the files in the container output do not match the evidence manifest")
    for path, digest in listed.items():
        if file_sha256(os.path.join(directory, path)) != digest:
            raise UntrustedOutput("%s does not match its recorded hash" % path)
    return evidence


def run_in_container(spec, policy, evidence_root, image=DEFAULT_IMAGE, offline=False, operation="REHEARSE_UPGRADE", progress=None, strict_licences=False):
    validate_python_name(spec.python_bin)
    if not docker_available():
        raise RuntimeError("Docker is not available, so the container runner cannot be used")
    digest = image_digest(image)
    if not digest:
        raise RuntimeError("the image %s does not exist; build it with: docker build -f Dockerfile.runner -t %s ." % (image, image))
    repo_path = os.path.realpath(spec.repo_path)
    source = describe_source(repo_path)
    request = request_from_parts(spec.run_id, repo_path, source, spec.to_dict(), policy.name, "", not offline, operation, "LOCAL", digest)
    schemas.require_valid("request", request)
    request_dir = tempfile.mkdtemp(prefix="ug-request-")
    out_dir = os.path.join(os.path.abspath(evidence_root), ".container-%s" % request["run_id"])
    os.makedirs(out_dir, exist_ok=True)
    try:
        with open(os.path.join(request_dir, "request.json"), "w") as handle:
            json.dump(request, handle)
        policy_file = spec.policy_path if spec.policy_path and os.path.isfile(spec.policy_path) else ""
        if policy_file:
            shutil.copyfile(policy_file, os.path.join(request_dir, "policy.json"))
        if progress:
            progress("running in a container")
        user = "%d:%d" % (os.getuid(), os.getgid())
        extra = ["--requirements", spec.requirements_file]
        for argument in spec.pytest_args:
            extra.append("--pytest-arg=%s" % argument)
        if spec.install_project:
            extra.append("--install-project")
        if strict_licences:
            extra.append("--strict-licences")
        if policy_file:
            extra += ["--policy", "/input/request/policy.json"]
        finished = run_command(docker_command(image, repo_path, request_dir, out_dir, digest, user, offline, extra=extra), timeout=7200)
        result_path = os.path.join(out_dir, "result.json")
        if not os.path.isfile(result_path):
            raise RuntimeError("the container finished without a result: %s" % finished["output"].strip()[-300:])
        if os.path.islink(result_path):
            raise UntrustedOutput("the container left a link instead of a result")
        result = schemas.require_valid("worker_result", read_json(result_path))
        if result["job_state"] != "SUCCEEDED":
            raise RuntimeError("the container job failed: %s" % result["error"])
        produced = os.path.join(out_dir, request["run_id"])
        verify_output(produced, request)
        final = os.path.join(os.path.abspath(evidence_root), request["run_id"])
        shutil.rmtree(final, ignore_errors=True)
        os.replace(produced, final)
        bundle = read_json(os.path.join(final, "bundle.json"))
        bundle["evidence_dir"] = final
        return bundle, request
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
