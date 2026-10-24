import io
import json
import os
import time
import zipfile

import pytest

from web import app as web_app
from web import security
from web.app import Settings, create_app


def fake_check(spec, policy, evidence_root, work_root, strict_licences=False, progress=None):
    os.makedirs(os.path.join(work_root, spec.run_id), exist_ok=True)
    if progress:
        progress("building before environment")
    if spec.package == "explode":
        raise RuntimeError("secret failure at /Users/someone/private/path")
    return {"verdict": {"decision": "Accept"}}


@pytest.fixture
def world(tmp_path):
    root = tmp_path / "project"
    (root / "examples" / "demo_repo").mkdir(parents=True)
    (root / "examples" / "demo_repo" / "requirements.txt").write_text("requests==2.28.2\n")
    (root / "policies").mkdir()
    (root / "policies" / "default.json").write_text("{}")
    (root / "evidence").mkdir()
    (tmp_path / "outside").mkdir()
    return root


def make_app(world, **changes):
    values = dict(
        project_root=str(world),
        evidence_root=str(world / "evidence"),
        work_root=str(world / "work"),
        policy_dir=str(world / "policies"),
        log_path=str(world / "logs" / "audit.log"),
        repo_bases=[os.path.realpath(str(world / "examples"))],
        access_token="",
        secret="test-secret",
        run_check=fake_check,
        requests_per_minute=10_000,
    )
    values.update(changes)
    return create_app(Settings(**values))


def csrf_pair(client):
    client.get("/")
    return client.get_cookie(security.CSRF_COOKIE).value


def good_form(token, **changes):
    form = {"csrf": token, "repo": "examples/demo_repo", "package": "requests", "from_version": "2.28.2",
            "to_version": "2.32.5", "policy": "default.json", "python": "python3"}
    form.update(changes)
    return form


def wait_until_done(client, run_id):
    for _ in range(100):
        if client.get("/runs/%s/state" % run_id).get_json()["state"] in ("finished", "failed"):
            return
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_pages_carry_security_headers(world):
    response = make_app(world).test_client().get("/")
    assert response.status_code == 200
    assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_pages_have_no_inline_script_or_style(world):
    html = make_app(world).test_client().get("/").get_data(as_text=True)
    assert "<script>" not in html and "style=" not in html


def test_debug_mode_is_off(world):
    assert make_app(world).debug is False


def test_a_post_without_the_csrf_token_is_refused(world):
    client = make_app(world).test_client()
    client.get("/")
    form = good_form("")
    assert client.post("/runs", data=form).status_code == 403


def test_a_post_with_a_wrong_csrf_token_is_refused(world):
    client = make_app(world).test_client()
    csrf_pair(client)
    assert client.post("/runs", data=good_form("not-the-token")).status_code == 403


def test_a_post_from_another_origin_is_refused(world):
    client = make_app(world).test_client()
    token = csrf_pair(client)
    response = client.post("/runs", data=good_form(token), headers={"Origin": "http://evil.example"})
    assert response.status_code == 403


def test_a_valid_post_starts_a_run_and_cleans_up_its_work_folder(world):
    client = make_app(world).test_client()
    token = csrf_pair(client)
    response = client.post("/runs", data=good_form(token))
    assert response.status_code == 302
    run_id = response.headers["Location"].rsplit("/", 1)[1]
    wait_until_done(client, run_id)
    time.sleep(0.2)
    assert not os.path.exists(os.path.join(str(world), "work", run_id))


@pytest.mark.parametrize("repo", ["../..", "/etc", "examples/../..", "examples/../../outside", "examples/missing", ""])
def test_repository_paths_outside_the_examples_are_refused(world, repo):
    client = make_app(world).test_client()
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token, repo=repo)).status_code == 400


def test_a_symlink_that_leaves_the_examples_folder_is_refused(world, tmp_path):
    os.symlink(str(tmp_path / "outside"), str(world / "examples" / "sneaky"))
    client = make_app(world).test_client()
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token, repo="examples/sneaky")).status_code == 400


@pytest.mark.parametrize("field,value", [
    ("package", "x\n-r /etc/passwd"), ("package", "--index-url=http://evil.example"), ("package", "a b"),
    ("from_version", "1.0\n--extra-index-url http://evil.example"), ("to_version", "2.0 ; rm -rf /"),
    ("to_version", "$(id)"), ("python", "/bin/sh"), ("python", "python3; id"), ("python", "../../bin/python3"),
])
def test_option_and_command_injection_is_refused(world, field, value):
    calls = []

    def spy(*args, **kwargs):
        calls.append(args)
        return fake_check(*args, **kwargs)

    client = make_app(world, run_check=spy).test_client()
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token, **{field: value})).status_code == 400
    assert calls == []


def test_run_ids_cannot_walk_out_of_the_evidence_folder(world):
    client = make_app(world).test_client()
    for path in ("/runs/..", "/runs/..%2f..%2fetc", "/runs/%2e%2e", "/runs/a%2fb", "/runs/.", "/runs/..%2foutside/report",
                 "/runs/..%2f..%2fetc/evidence.zip"):
        assert client.get(path).status_code == 404, path


def test_a_symlinked_run_folder_cannot_escape(world, tmp_path):
    os.symlink(str(tmp_path / "outside"), str(world / "evidence" / "linked-run"))
    (tmp_path / "outside" / "report.html").write_text("secret")
    client = make_app(world).test_client()
    assert client.get("/runs/linked-run/report").status_code == 404


def write_run(world, run_id, package="requests"):
    directory = world / "evidence" / run_id
    directory.mkdir()
    (directory / "verdict.json").write_text(json.dumps({"decision": "Accept"}))
    (directory / "run.json").write_text(json.dumps({"package": package, "from_version": "1", "to_version": "2",
                                                    "repo_path": "/x/demo"}))
    return directory


def test_run_list_escapes_hostile_values(world):
    write_run(world, "run-one", package="<script>alert(1)</script>")
    html = make_app(world).test_client().get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_reports_get_a_locked_down_policy(world):
    directory = write_run(world, "run-two")
    (directory / "report.html").write_text("<html><body>report</body></html>")
    response = make_app(world).test_client().get("/runs/run-two/report")
    assert response.status_code == 200
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "script" not in response.headers["Content-Security-Policy"]


def test_the_evidence_zip_hides_host_paths(world):
    directory = write_run(world, "run-three")
    (directory / "bundle.json").write_text(json.dumps({"evidence_dir": str(world / "evidence" / "run-three")}))
    response = make_app(world).test_client().get("/runs/run-three/evidence.zip")
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.data))
    text = archive.read("run-three/bundle.json").decode()
    assert str(world) not in text
    assert "<project>" in text


def test_a_failed_run_never_leaks_the_exception_text(world):
    client = make_app(world).test_client()
    token = csrf_pair(client)
    response = client.post("/runs", data=good_form(token, package="explode"))
    run_id = response.headers["Location"].rsplit("/", 1)[1]
    wait_until_done(client, run_id)
    page = client.get("/runs/%s" % run_id).get_data(as_text=True)
    assert "secret failure" not in page and "/Users/someone" not in page
    assert "could not finish" in page


def test_error_pages_do_not_show_a_stack_trace(world):
    response = make_app(world).test_client().get("/nowhere")
    assert response.status_code == 404
    assert "Traceback" not in response.get_data(as_text=True)


def test_large_bodies_are_refused(world):
    client = make_app(world).test_client()
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token, package="a" * 20000)).status_code == 413


def test_run_quota_per_client(world):
    client = make_app(world, runs_per_hour=1).test_client()
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token)).status_code == 302
    assert client.post("/runs", data=good_form(token)).status_code == 429


def test_the_site_refuses_new_runs_when_busy(world):
    client = make_app(world, max_active_runs=0).test_client()
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token)).status_code == 429


def test_request_rate_limit(world):
    client = make_app(world, requests_per_minute=3).test_client()
    codes = [client.get("/").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and 429 in codes[3:]


def test_everything_except_the_landing_page_needs_login_when_a_token_is_set(world):
    client = make_app(world, access_token="letmein").test_client()
    assert client.get("/").status_code == 200
    assert "Access token" in client.get("/").get_data(as_text=True)
    for path in ("/runs/anything", "/runs/anything/state", "/runs/anything/report", "/runs/anything/evidence.zip"):
        assert client.get(path).status_code == 401, path
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token)).status_code == 401


def test_landing_page_hides_runs_from_anonymous_visitors(world):
    write_run(world, "run-four")
    html = make_app(world, access_token="letmein").test_client().get("/").get_data(as_text=True)
    assert "run-four" not in html


def test_wrong_token_is_refused_and_right_token_logs_in(world):
    client = make_app(world, access_token="letmein").test_client()
    token = csrf_pair(client)
    assert client.post("/login", data={"csrf": token, "token": "wrong"}).status_code == 400
    assert client.get_cookie(security.SESSION_COOKIE) is None
    assert client.post("/login", data={"csrf": token, "token": "letmein"}).status_code == 302
    cookie = client.get_cookie(security.SESSION_COOKIE)
    assert cookie is not None
    assert client.get("/runs/missing").status_code == 404


def test_a_forged_session_cookie_is_refused(world):
    client = make_app(world, access_token="letmein").test_client()
    client.set_cookie(security.SESSION_COOKIE, "9999999999.deadbeef")
    assert client.get("/runs/missing").status_code == 401


def test_login_attempts_are_rate_limited(world):
    client = make_app(world, access_token="letmein", logins_per_minute=2).test_client()
    token = csrf_pair(client)
    codes = [client.post("/login", data={"csrf": token, "token": "bad"}).status_code for _ in range(4)]
    assert codes[:2] == [400, 400] and 429 in codes[2:]


def test_the_server_will_not_listen_publicly_without_a_token(monkeypatch):
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.delenv("UPGRADEGUARD_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(web_app, "Settings", lambda: Settings(access_token=""))
    with pytest.raises(SystemExit):
        web_app.run_server()


def test_session_signature_and_expiry():
    gate = security.AccessGate("t", "s")
    cookie = gate.make_session(now=1000)
    assert gate.session_is_valid(cookie, now=1001)
    assert not gate.session_is_valid(cookie, now=1000 + security.SESSION_SECONDS + 1)
    assert not gate.session_is_valid(cookie + "0", now=1001)
    assert not gate.session_is_valid("", now=1001)
    assert not security.AccessGate("", "s").token_is_valid("anything")


def test_rate_limiter_window_slides():
    limiter = security.RateLimiter(2, 10)
    assert limiter.allow("a", now=0) and limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.allow("b", now=2)
    assert limiter.allow("a", now=11)


@pytest.mark.parametrize("run_id", ["a b", "a/b", "a\nb", "a;b", "run\x00x", ""])
def test_run_id_pattern_rejects_odd_characters(run_id):
    assert web_app.RUN_ID_PATTERN.fullmatch(run_id) is None


def test_a_deployment_that_requires_a_token_refuses_to_start_without_one(world, monkeypatch):
    monkeypatch.setenv("UPGRADEGUARD_REQUIRE_TOKEN", "1")
    with pytest.raises(RuntimeError):
        make_app(world)
    assert make_app(world, access_token="set") is not None


def fake_lookup(name):
    return {"status": "found", "latest": "9.9", "summary": "demo", "licence": "MIT", "requires_python": ""}


def test_health_check_reads_pasted_text_and_saves_it_in_the_history(world):
    client = make_app(world, history_path=str(world / "h.db"), lookup_metadata=fake_lookup).test_client()
    token = csrf_pair(client)
    response = client.post("/health", data={"csrf": token, "text": "flask==3.0.0\nnumpy>=1.24\nnumpy==1.26.4\n", "policy": "default.json"})
    assert response.status_code == 302
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Dependency health report" in page and "numpy" in page and "92" in page
    assert "Dependency health" in client.get("/history").get_data(as_text=True)


def test_health_check_accepts_a_file_upload_and_refuses_oversized_or_empty_input(world):
    client = make_app(world, history_path=str(world / "h.db"), lookup_metadata=fake_lookup).test_client()
    token = csrf_pair(client)
    upload = client.post("/health", data={"csrf": token, "file": (io.BytesIO(b"requests==2.0\n"), "requirements.txt")}, content_type="multipart/form-data")
    assert upload.status_code == 302
    assert client.post("/health", data={"csrf": token, "text": ""}).status_code == 400
    assert client.post("/health", data={"csrf": token, "text": "x" * 250_000}).status_code == 413


def test_health_pages_escape_hostile_package_text(world):
    client = make_app(world, history_path=str(world / "h.db"), lookup_metadata=fake_lookup).test_client()
    token = csrf_pair(client)
    response = client.post("/health", data={"csrf": token, "text": "<script>alert(1)</script>==1\n"})
    body = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "<script>alert(1)" not in body


def test_health_check_needs_the_csrf_token(world):
    client = make_app(world, history_path=str(world / "h.db")).test_client()
    csrf_pair(client)
    assert client.post("/health", data={"text": "flask"}).status_code == 403


def test_finished_runs_are_listed_in_the_history_after_a_restart(world):
    path = str(world / "h.db")
    client = make_app(world, history_path=path).test_client()
    token = csrf_pair(client)
    run_id = client.post("/runs", data=good_form(token)).headers["Location"].rsplit("/", 1)[1]
    for _ in range(100):
        if client.get("/runs/%s/state" % run_id).get_json()["state"] != "queued" and "finished" in client.get("/runs/%s/state" % run_id).get_json()["state"]:
            break
        time.sleep(0.05)
    assert "requests 2.28.2 to 2.32.5" in make_app(world, history_path=path).test_client().get("/history").get_data(as_text=True)


def test_settings_lists_servers_without_secrets_and_cannot_add_one(world):
    profiles = world / "profiles.json"
    profiles.write_text(json.dumps({"profiles": {"demo": {"host": "build.example.org", "user": "azureuser", "identity_file": "/keys/secret-id", "known_hosts_file": "/keys/known",
                                                          "worker_dir": "/srv/ug", "jobs_dir": "/srv/jobs"}}}))
    client = make_app(world, remote_profiles_path=str(profiles), history_path=str(world / "h.db")).test_client()
    page = client.get("/settings").get_data(as_text=True)
    assert "build.example.org" in page and "secret-id" not in page
    token = csrf_pair(client)
    assert client.post("/settings/test", data={"csrf": token, "profile": "not-a-profile"}).status_code == 404
    assert "Server: demo" in client.get("/").get_data(as_text=True)


def test_a_remote_run_only_accepts_a_server_that_is_configured(world):
    client = make_app(world, history_path=str(world / "h.db")).test_client()
    token = csrf_pair(client)
    assert client.post("/runs", data=good_form(token, location="evil.example.org")).status_code == 400


def test_a_server_problem_is_shown_as_not_an_upgrade_verdict(world):
    from upgradeguard.remote import RemoteError

    def broken(spec, policy, profile, evidence_root, progress=None, cancelled=None, options=None):
        raise RemoteError("connection", "could not reach the server")

    profiles = world / "profiles.json"
    profiles.write_text(json.dumps({"profiles": {"demo": {"host": "build.example.org", "user": "azureuser", "identity_file": "/keys/id", "known_hosts_file": "/keys/known",
                                                          "worker_dir": "/srv/ug", "jobs_dir": "/srv/jobs"}}}))
    client = make_app(world, remote_profiles_path=str(profiles), run_remote=broken, history_path=str(world / "h.db")).test_client()
    token = csrf_pair(client)
    run_id = client.post("/runs", data=good_form(token, location="demo")).headers["Location"].rsplit("/", 1)[1]
    for _ in range(100):
        state = client.get("/runs/%s/state" % run_id).get_json()
        if state["state"] == "failed":
            break
        time.sleep(0.05)
    assert "says nothing about the upgrade" in state["error"] and "could not reach the server" in state["error"]


def test_a_browser_form_post_with_a_null_origin_is_accepted_but_cross_site_is_not(world):
    client = make_app(world, history_path=str(world / "h.db")).test_client()
    token = csrf_pair(client)
    same = {"Origin": "null", "Sec-Fetch-Site": "same-origin"}
    assert client.post("/runs", data=good_form(token), headers=same).status_code == 302
    cross = {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}
    assert client.post("/runs", data=good_form(token), headers=cross).status_code == 403
    assert client.post("/runs", data=good_form(token), headers={"Origin": "https://evil.example"}).status_code == 403
