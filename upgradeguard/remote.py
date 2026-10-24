import json
import os
import re
import shlex
import shutil
import tempfile
import time
from dataclasses import dataclass

from . import schemas
from .container import UntrustedOutput, check_bundle_matches, copy_output, verify_output
from .contract import request_from_parts
from .source import build_manifest, describe_source, safe_extract, write_archive
from .spec import validate_python_name
from .util import read_json, run_command, write_json

HOST = re.compile(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")
USER = re.compile(r"[a-z_][a-z0-9_-]{0,31}")
PROFILE_NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
ABSOLUTE = re.compile(r"/[A-Za-z0-9_./-]{1,200}")
MIN_PYTHON = (3, 9)
MIN_DISK_MB = 1024
POLL_SECONDS = 3
MAX_OUTPUT_BYTES = 500 * 1024 * 1024


class RemoteError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


@dataclass
class Profile:
    name: str
    host: str
    user: str
    port: int
    identity_file: str
    known_hosts_file: str
    worker_dir: str
    jobs_dir: str
    python: str
    timeout_seconds: int


def check_path(value, label):
    if not ABSOLUTE.fullmatch(value) or ".." in value.split("/"):
        raise ValueError("%s must be a plain absolute path" % label)
    return value


def make_profile(name, raw):
    if not PROFILE_NAME.fullmatch(name):
        raise ValueError("bad profile name")
    host, user = str(raw.get("host", "")), str(raw.get("user", ""))
    if not HOST.fullmatch(host) or host.startswith("-"):
        raise ValueError("bad host in profile %s" % name)
    if not USER.fullmatch(user):
        raise ValueError("bad user in profile %s" % name)
    port = int(raw.get("port", 22))
    if not 1 <= port <= 65535:
        raise ValueError("bad port in profile %s" % name)
    return Profile(name, host, user, port, check_path(raw["identity_file"], "identity_file"), check_path(raw["known_hosts_file"], "known_hosts_file"),
                   check_path(raw["worker_dir"], "worker_dir"), check_path(raw["jobs_dir"], "jobs_dir"), check_path(raw.get("python", raw["worker_dir"] + "/venv/bin/python"), "python"),
                   max(60, min(int(raw.get("timeout_seconds", 3600)), 24 * 3600)))


def load_profiles(path):
    if not path or not os.path.isfile(path):
        return {}
    raw = read_json(path)
    return {name: make_profile(name, item) for name, item in raw.get("profiles", {}).items()}


class Remote:
    def __init__(self, profile, run=run_command):
        self.profile = profile
        self.run = run

    def options(self):
        profile = self.profile
        return ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "UserKnownHostsFile=%s" % profile.known_hosts_file, "-o", "IdentitiesOnly=yes",
                "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", "-i", profile.identity_file]

    def target(self):
        return "%s@%s" % (self.profile.user, self.profile.host)

    def command_line(self, words):
        if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:+-]{0,99}", word) for word in words):
            raise ValueError("a remote command word was refused")
        profile = self.profile
        return "cd %s && %s -m upgradeguard.remote_worker --root %s %s" % (
            shlex.quote(profile.worker_dir), shlex.quote(profile.python), shlex.quote(profile.jobs_dir), " ".join(shlex.quote(word) for word in words))

    def ssh_args(self, words):
        return ["ssh", "-p", str(self.profile.port)] + self.options() + ["--", self.target(), self.command_line(words)]

    def scp_args(self, source, destination):
        return ["scp", "-q", "-P", str(self.profile.port)] + self.options() + ["--", source, destination]

    def call(self, *words, timeout=120):
        finished = self.run(self.ssh_args(list(words)), timeout=timeout)
        if finished["timed_out"]:
            raise RemoteError("connection", "the remote command timed out")
        if finished["returncode"] == 255 or finished["returncode"] == -1:
            raise RemoteError("connection", "could not reach the server: %s" % finished["output"].strip()[-200:])
        try:
            answer = json.loads(finished["output"].strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise RemoteError("worker", "the worker gave an unreadable answer: %s" % finished["output"].strip()[-200:])
        if finished["returncode"] != 0 or "error" in answer:
            raise RemoteError("worker", answer.get("error", "the worker failed"))
        return answer

    def upload(self, local, name, job):
        destination = "%s:%s/%s/%s" % (self.target(), self.profile.jobs_dir, job, name)
        finished = self.run(self.scp_args(local, destination), timeout=1800)
        if finished["returncode"] != 0:
            raise RemoteError("connection", "upload failed: %s" % finished["output"].strip()[-200:])

    def download(self, job, name, local):
        source = "%s:%s/%s/%s" % (self.target(), self.profile.jobs_dir, job, name)
        finished = self.run(self.scp_args(source, local), timeout=1800)
        if finished["returncode"] != 0:
            raise RemoteError("connection", "download failed: %s" % finished["output"].strip()[-200:])


def preflight(remote):
    caps = remote.call("capabilities")
    version = tuple(int(part) for part in caps["python"].split(".")[:2])
    if version < MIN_PYTHON:
        raise RemoteError("preflight", "the server has Python %s; %d.%d or newer is needed" % (caps["python"], *MIN_PYTHON))
    if caps["disk_free_mb"] < MIN_DISK_MB:
        raise RemoteError("preflight", "the server has only %d MB free" % caps["disk_free_mb"])
    return caps


def stop_job(remote, job):
    try:
        return remote.call("cancel", job).get("confirmed_stopped", False)
    except RemoteError:
        return False


def wait_for_job(remote, job, timeout, progress, cancelled, sleep=time.sleep):
    deadline = time.time() + timeout
    while True:
        if cancelled and cancelled():
            confirmed = stop_job(remote, job)
            raise RemoteError("cancelled", "the check was cancelled" + ("" if confirmed else "; the server could not confirm the job stopped"))
        state = remote.call("status", job)
        if state["state"] != "RUNNING":
            return state
        if time.time() > deadline:
            confirmed = stop_job(remote, job)
            raise RemoteError("timeout", "the check ran longer than %d seconds and was stopped" % timeout + ("" if confirmed else "; stopping it could not be confirmed"))
        if progress:
            progress("running on %s" % remote.profile.host)
        sleep(POLL_SECONDS)


def safe_download_extract(archive, destination):
    import tarfile
    try:
        with tarfile.open(archive, "r:gz") as handle:
            if sum(member.size for member in handle.getmembers()) > MAX_OUTPUT_BYTES:
                raise UntrustedOutput("the server output is larger than %d bytes" % MAX_OUTPUT_BYTES)
            for member in handle.getmembers():
                if not (member.isfile() or member.isdir()):
                    raise UntrustedOutput("the server output contains %s, which is not a plain file" % member.name)
        safe_extract(archive, destination)
    except (ValueError, tarfile.TarError) as problem:
        raise UntrustedOutput("the server output was refused: %s" % problem)


def run_remote(spec, policy, profile, evidence_root, progress=None, cancelled=None, run=run_command, sleep=time.sleep, options=None):
    validate_python_name(spec.python_bin)
    remote = Remote(profile, run)
    repo_path = os.path.realpath(spec.repo_path)
    source = describe_source(repo_path)
    request = request_from_parts(spec.run_id, repo_path, source, spec.to_dict(), policy.name, "", True, "REHEARSE_UPGRADE", "AZURE_VM")
    schemas.require_valid("request", request)
    job = request["run_id"]
    staging = tempfile.mkdtemp(prefix="ug-remote-")
    started_cleanup = False
    try:
        if progress:
            progress("checking the server")
        capabilities = preflight(remote)
        remote.call("init", job)
        started_cleanup = True
        archive = write_archive(repo_path, build_manifest(repo_path), os.path.join(staging, "source.tar.gz"))
        write_json(os.path.join(staging, "request.json"), request)
        write_json(os.path.join(staging, "options.json"), {"requirements": spec.requirements_file, "install_project": spec.install_project, **(options or {})})
        if progress:
            progress("sending the project")
        remote.upload(archive, "source.tar.gz", job)
        remote.upload(os.path.join(staging, "request.json"), "request.json", job)
        remote.upload(os.path.join(staging, "options.json"), "options.json", job)
        if spec.policy_path and os.path.isfile(spec.policy_path):
            remote.upload(spec.policy_path, "policy.json", job)
        remote.call("prepare", job)
        remote.call("start", job)
        state = wait_for_job(remote, job, profile.timeout_seconds, progress, cancelled, sleep)
        if state["state"] != "SUCCEEDED":
            raise RemoteError("worker", "the job on the server ended as %s" % state["state"])
        remote.call("package", job)
        local_archive = os.path.join(staging, "out.tar.gz")
        remote.download(job, "out.tar.gz", local_archive)
        extracted = os.path.join(staging, "extracted")
        os.makedirs(extracted)
        safe_download_extract(local_archive, extracted)
        trusted = os.path.join(staging, "trusted")
        copy_output(extracted, trusted)
        result = schemas.require_valid("worker_result", read_json(os.path.join(trusted, "result.json")))
        if result["job_state"] != "SUCCEEDED":
            raise RemoteError("worker", "the remote job failed: %s" % result["error"])
        produced = os.path.join(trusted, request["run_id"])
        evidence = verify_output(produced, request)
        bundle = read_json(os.path.join(produced, "bundle.json"))
        check_bundle_matches(bundle, evidence, request)
        final = os.path.join(os.path.abspath(evidence_root), request["run_id"])
        shutil.rmtree(final, ignore_errors=True)
        shutil.move(produced, final)
        write_json(os.path.join(final, "remote.json"), {"profile": profile.name, "host": profile.host, "worker_version": capabilities["worker_version"],
                                                        "python": capabilities["python"], "platform": capabilities["platform"], "verified": True})
        bundle["evidence_dir"] = final
        return bundle, request
    except UntrustedOutput as problem:
        raise RemoteError("output", str(problem))
    finally:
        if started_cleanup:
            try:
                remote.call("cleanup", job)
            except RemoteError:
                pass
        shutil.rmtree(staging, ignore_errors=True)


def test_connection(profile, run=run_command):
    return preflight(Remote(profile, run))
