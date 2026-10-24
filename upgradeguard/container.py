import json
import os
import shutil
import stat
import tempfile

from . import schemas
from .contract import file_sha256, request_from_parts
from .source import describe_source
from .spec import canonical_name
from .spec import canonical_name, validate_python_name
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


def stop_container(name):
    run_command(["docker", "rm", "-f", name], timeout=120)


def copy_output(source, destination):
    for current, folders, names in os.walk(source, followlinks=False):
        for entry in folders + names:
            if os.path.islink(os.path.join(current, entry)):
                raise UntrustedOutput("the container left a link at %s" % os.path.relpath(os.path.join(current, entry), source))
        target = os.path.join(destination, os.path.relpath(current, source))
        os.makedirs(target, exist_ok=True)
        for name in names:
            if not stat.S_ISREG(os.lstat(os.path.join(current, name)).st_mode):
                raise UntrustedOutput("the container left a file that is not a regular file")
            descriptor = os.open(os.path.join(current, name), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise UntrustedOutput("the container left a file that is not a regular file")
                with os.fdopen(descriptor, "rb") as handle, open(os.path.join(target, name), "wb") as sink:
                    shutil.copyfileobj(handle, sink)
            except BaseException:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                raise


def check_bundle_matches(bundle, evidence, request):
    wanted = {"ACCEPT": "Accept", "REJECT": "Reject", "INSUFFICIENT_EVIDENCE": "Insufficient Evidence"}
    change = request["change"]
    if bundle["verdict"]["decision"] != wanted[evidence["verdict"]["decision"]]:
        raise UntrustedOutput("the bundle and the evidence disagree about the verdict")
    spec = bundle["spec"]
    if (canonical_name(spec["package"]), spec["from_version"], spec["to_version"]) != (change["package"], change["from_version"], change["to_version"]):
        raise UntrustedOutput("the bundle describes a different change from the one requested")
    if evidence["request"]["change"] != change or evidence["request"]["operation"] != request["operation"]:
        raise UntrustedOutput("the evidence describes a different job from the one requested")


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
        name = "ug-%s" % request["run_id"]
        finished = run_command(docker_command(image, repo_path, request_dir, out_dir, digest, user, offline, name=name, extra=extra), timeout=7200)
        stop_container(name)
        if finished["timed_out"]:
            raise RuntimeError("the container job timed out and was stopped")
        result_path = os.path.join(out_dir, "result.json")
        if not os.path.isfile(result_path):
            raise RuntimeError("the container finished without a result: %s" % finished["output"].strip()[-300:])
        trusted = tempfile.mkdtemp(prefix="ug-output-")
        try:
            copy_output(out_dir, trusted)
            result = schemas.require_valid("worker_result", read_json(os.path.join(trusted, "result.json")))
            if result["job_state"] != "SUCCEEDED":
                raise RuntimeError("the container job failed: %s" % result["error"])
            produced = os.path.join(trusted, request["run_id"])
            evidence = verify_output(produced, request)
            bundle = read_json(os.path.join(produced, "bundle.json"))
            check_bundle_matches(bundle, evidence, request)
            final = os.path.join(os.path.abspath(evidence_root), request["run_id"])
            shutil.rmtree(final, ignore_errors=True)
            shutil.move(produced, final)
            bundle["evidence_dir"] = final
            return bundle, request
        finally:
            shutil.rmtree(trusted, ignore_errors=True)
    finally:
        shutil.rmtree(request_dir, ignore_errors=True)
        shutil.rmtree(out_dir, ignore_errors=True)
