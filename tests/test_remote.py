import contextlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import time

import pytest

from upgradeguard import remote, remote_worker
from upgradeguard.spec import UpgradeSpec, load_policy

REMOTE_JOBS = "/srv/ug-jobs"
PROFILE = {"host": "build.example.org", "user": "azureuser", "port": 22, "identity_file": "/keys/id", "known_hosts_file": "/keys/known",
           "worker_dir": "/srv/ug", "jobs_dir": REMOTE_JOBS, "python": "/srv/ug/venv/bin/python", "timeout_seconds": 600}


def profile(**changes):
    return remote.make_profile("demo", {**PROFILE, **changes})


def project(tmp_path):
    path = tmp_path / "project"
    path.mkdir()
    (path / "requirements.txt").write_text("six==1.16.0\n")
    (path / "test_x.py").write_text("def test_ok():\n    assert True\n")
    (path / ".env").write_text("SECRET=1\n")
    return path


class FakeServer:
    """Stands in for ssh and scp. It runs the real remote_worker commands in a temp folder, but its job output is canned. This is a fake, not a real server."""

    def __init__(self, tmp_path, caps=None, final_state="SUCCEEDED", tamper=None):
        self.jobs = tmp_path / "server-jobs"
        self.jobs.mkdir()
        self.calls, self.caps, self.final_state, self.tamper = [], caps, final_state, tamper
        self.unreachable = False

    def real(self, remote_path):
        return str(self.jobs) + remote_path[len(REMOTE_JOBS):]

    def run(self, args, timeout=0, **_):
        self.calls.append(args)
        if self.unreachable:
            return {"returncode": 255, "output": "ssh: connect to host build.example.org port 22: Connection refused", "timed_out": False}
        divider = args.index("--")
        if args[0] == "scp":
            source, destination = args[divider + 1], args[divider + 2]
            if ":" in source and not source.startswith("/"):
                shutil.copyfile(self.real(source.split(":", 1)[1]), destination)
            else:
                target = self.real(destination.split(":", 1)[1])
                shutil.copyfile(source, target)
            return {"returncode": 0, "output": "", "timed_out": False}
        words = shlex.split(args[divider + 2].split("--root", 1)[1])
        words[0] = str(self.jobs)
        if words[1] == "capabilities" and self.caps:
            return {"returncode": 0, "output": json.dumps(self.caps), "timed_out": False}
        if words[1] == "start":
            self.finish_job(os.path.join(words[0], words[2]))
            return {"returncode": 0, "output": json.dumps({"started": True}), "timed_out": False}
        if words[1] == "status" and self.final_state != "SUCCEEDED":
            return {"returncode": 0, "output": json.dumps({"state": self.final_state, "exit": 1}), "timed_out": False}
        buffer = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(buffer):
            try:
                remote_worker.main(["--root"] + words)
            except SystemExit as stop:
                code = stop.code
        return {"returncode": code, "output": buffer.getvalue(), "timed_out": False}

    def finish_job(self, folder):
        from test_worker_container import sample_output
        request = json.load(open(os.path.join(folder, "request.json")))
        scratch = os.path.join(folder, "scratch")
        os.makedirs(scratch)
        import pathlib
        directory, built = sample_output(pathlib.Path(scratch), request)
        from upgradeguard.contract import file_sha256
        change = request["change"]
        (directory / "bundle.json").write_text(json.dumps({"verdict": {"decision": "Reject"}, "spec": {"package": change["package"],
                                                           "from_version": change["from_version"], "to_version": change["to_version"]}}))
        evidence_path = directory / "evidence.json"
        evidence = json.loads(evidence_path.read_text())
        evidence["artifact_manifest"][0]["sha256"] = file_sha256(str(directory / "bundle.json"))
        evidence_path.write_text(json.dumps(evidence))
        out = os.path.join(folder, "out")
        shutil.copytree(os.path.dirname(directory), out)
        result = {"schema_version": "1.0.0", "run_id": request["run_id"], "operation": request["operation"], "job_state": "SUCCEEDED",
                  "verdict": "REJECT", "evidence_path": "x/evidence.json", "error": None, "started_at": "2026-10-24T10:00:00Z", "finished_at": "2026-10-24T10:01:00Z"}
        json.dump(result, open(os.path.join(out, "result.json"), "w"))
        if self.tamper:
            self.tamper(out, request["run_id"])
        open(os.path.join(folder, "exit"), "w").write("0")


def spec_for(path):
    return UpgradeSpec(repo_path=str(path), package="six", from_version="1.16.0", to_version="1.17.0", run_id="run-worker-test")


def check(tmp_path, server, **kwargs):
    return remote.run_remote(spec_for(project(tmp_path)), load_policy(""), profile(), str(tmp_path / "evidence"), run=server.run, sleep=lambda _: None, **kwargs)


def test_a_clean_remote_run_returns_verified_evidence_and_cleans_up(tmp_path):
    server = FakeServer(tmp_path)
    bundle, request = check(tmp_path, server)
    assert request["execution_provider"] == "AZURE_VM"
    final = tmp_path / "evidence" / "run-worker-test"
    assert (final / "evidence.json").is_file() and json.load(open(final / "remote.json"))["host"] == "build.example.org"
    assert not (server.jobs / "run-worker-test").exists()


def test_secrets_are_not_in_the_archive_that_is_sent(tmp_path):
    server = FakeServer(tmp_path)
    sent = []
    original = server.run

    def spy(args, **kwargs):
        if args[0] == "scp" and args[-2].endswith("source.tar.gz"):
            with tarfile.open(args[-2]) as archive:
                sent.extend(archive.getnames())
        return original(args, **kwargs)

    server.run = spy
    check(tmp_path, server)
    assert "requirements.txt" in sent and ".env" not in sent


def test_ssh_is_called_with_checked_options_and_one_fixed_command(tmp_path):
    server = FakeServer(tmp_path)
    check(tmp_path, server)
    first = server.calls[0]
    assert first[0] == "ssh" and "BatchMode=yes" in first and "StrictHostKeyChecking=yes" in first and "UserKnownHostsFile=/keys/known" in first
    assert first[first.index("--") + 1] == "azureuser@build.example.org"
    assert len(first) == first.index("--") + 3
    assert first[-1].startswith("cd /srv/ug && /srv/ug/venv/bin/python -m upgradeguard.remote_worker --root /srv/ug-jobs capabilities")


@pytest.mark.parametrize("changes", [{"host": "-oProxyCommand=x"}, {"host": "a b"}, {"host": "a;b"}, {"user": "root name"}, {"user": "-x"}, {"port": 0}, {"port": 70000},
                                     {"identity_file": "keys/id"}, {"jobs_dir": "/srv/../etc"}, {"worker_dir": "/srv/ug; rm -rf /"}])
def test_hostile_profile_values_are_refused(changes):
    with pytest.raises(ValueError):
        profile(**changes)


@pytest.mark.parametrize("word", ["a b", "a;b", "$(id)", "-x", "", "a" * 101])
def test_remote_command_words_are_checked(word):
    with pytest.raises(ValueError):
        remote.Remote(profile()).command_line(["status", word])


def test_profiles_come_from_a_server_side_file_only(tmp_path):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"profiles": {"demo": PROFILE}}))
    assert list(remote.load_profiles(str(path))) == ["demo"]
    assert remote.load_profiles(str(tmp_path / "missing.json")) == {}
    assert remote.load_profiles("") == {}


def test_an_unreachable_server_is_a_connection_error_not_a_verdict(tmp_path):
    server = FakeServer(tmp_path)
    server.unreachable = True
    with pytest.raises(remote.RemoteError) as caught:
        check(tmp_path, server)
    assert caught.value.kind == "connection" and "Connection refused" in str(caught.value)


@pytest.mark.parametrize("caps,needle", [({"worker_version": "1", "python": "3.8.10", "platform": "linux", "disk_free_mb": 9000}, "3.8.10"),
                                         ({"worker_version": "1", "python": "3.12.3", "platform": "linux", "disk_free_mb": 10}, "10 MB")])
def test_preflight_refuses_an_unsuitable_server(tmp_path, caps, needle):
    with pytest.raises(remote.RemoteError) as caught:
        check(tmp_path, FakeServer(tmp_path, caps=caps))
    assert caught.value.kind == "preflight" and needle in str(caught.value)


def test_a_failed_remote_job_is_a_worker_error_and_is_still_cleaned_up(tmp_path):
    server = FakeServer(tmp_path, final_state="FAILED")
    with pytest.raises(remote.RemoteError) as caught:
        check(tmp_path, server)
    assert caught.value.kind == "worker"
    assert any("cleanup" in call[-1] for call in server.calls if call[0] == "ssh")


def test_cancelling_stops_the_remote_job(tmp_path):
    server = FakeServer(tmp_path)
    server.final_state = "RUNNING"
    with pytest.raises(remote.RemoteError) as caught:
        check(tmp_path, server, cancelled=lambda: True)
    assert caught.value.kind == "cancelled"
    assert any(" cancel " in call[-1] for call in server.calls if call[0] == "ssh")


def test_a_job_that_runs_too_long_is_stopped_and_reported(tmp_path):
    server = FakeServer(tmp_path, final_state="RUNNING")
    with pytest.raises(remote.RemoteError) as caught:
        remote.wait_for_job(remote.Remote(profile(), server.run), "run-worker-test", -1, None, None, lambda _: None)
    assert caught.value.kind == "timeout"


def extra_file(out, run_id):
    open(os.path.join(out, run_id, "extra.txt"), "w").write("not in the manifest")


def wrong_job(out, run_id):
    path = os.path.join(out, run_id, "evidence.json")
    data = json.load(open(path))
    data["request"]["run_id"] = "someone-elses-job"
    json.dump(data, open(path, "w"))


@pytest.mark.parametrize("tamper", [extra_file, wrong_job])
def test_untrusted_server_output_is_refused(tmp_path, tamper):
    with pytest.raises(remote.RemoteError) as caught:
        check(tmp_path, FakeServer(tmp_path, tamper=tamper))
    assert caught.value.kind == "output"
    assert not (tmp_path / "evidence" / "run-worker-test").exists()


def test_a_download_with_path_traversal_is_refused(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 1
        handle.addfile(info, io.BytesIO(b"x"))
    with pytest.raises(remote.UntrustedOutput):
        remote.safe_download_extract(str(archive), str(tmp_path / "x"))
    assert not (tmp_path / "escape.txt").exists()


def test_a_download_containing_a_link_is_refused(tmp_path):
    archive = tmp_path / "link.tar.gz"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("leak")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        handle.addfile(info)
    with pytest.raises(remote.UntrustedOutput):
        remote.safe_download_extract(str(archive), str(tmp_path / "x"))


def test_the_remote_worker_refuses_bad_job_ids_and_roots(tmp_path, capsys):
    for words in (["--root", str(tmp_path), "init", "../x"], ["--root", "relative", "init", "job"], ["--root", "/a/../b", "init", "job"],
                  ["--root", str(tmp_path), "bogus", "job"]):
        with pytest.raises(SystemExit):
            remote_worker.main(words)


def test_the_remote_worker_refuses_a_hostile_archive(tmp_path, capsys):
    folder = tmp_path / "job"
    folder.mkdir()
    with tarfile.open(folder / "source.tar.gz", "w:gz") as handle:
        info = tarfile.TarInfo("../../escape")
        info.size = 0
        handle.addfile(info, io.BytesIO(b""))
    with pytest.raises(SystemExit):
        remote_worker.prepare(str(folder))
    assert "refused" in capsys.readouterr().out


def test_cancel_kills_the_whole_remote_process_group(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    process = subprocess.Popen(["sleep", "60"], start_new_session=True)
    (folder / "pid").write_text(str(process.pid))
    answer = remote_worker.cancel(str(folder))
    assert answer["confirmed_stopped"] is True and not remote_worker.alive(process.pid)
    assert remote_worker.status(str(folder))["state"] == "CANCELLED"


def test_status_reports_running_and_failed(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    (folder / "pid").write_text(str(os.getpid()))
    assert remote_worker.status(str(folder))["state"] == "RUNNING"
    (folder / "pid").write_text("999999")
    assert remote_worker.status(str(folder))["state"] == "FAILED"


@pytest.mark.slow
def test_real_worker_through_a_fake_ssh_on_this_machine(tmp_path, monkeypatch):
    """Fake ssh and scp that run locally, but the remote worker and the verification are real. Needs network for pip."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.setenv("PATH", os.path.join(root, "tests", "fake_ssh") + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("PYTHONPATH", root)
    jobs = tmp_path / "jobs"
    local = remote.make_profile("local", {**PROFILE, "worker_dir": root, "jobs_dir": str(jobs), "python": sys.executable, "timeout_seconds": 1800})
    spec = UpgradeSpec(repo_path=os.path.join(root, "examples", "demo_repo"), package="requests", from_version="2.28.2", to_version="2.32.5",
                       run_id="remote-real-test")
    bundle, request = remote.run_remote(spec, load_policy(""), local, str(tmp_path / "evidence"))
    assert bundle["verdict"]["decision"] == "Accept"
    assert (tmp_path / "evidence" / "remote-real-test" / "remote.json").is_file()
    assert not (jobs / "remote-real-test").exists()
