import io
import logging
import os
import re
import secrets
import shutil
import sys
import threading
import zipfile
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler

from flask import Flask, abort, make_response, redirect, render_template, request, send_file, url_for

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from web import security
from upgradeguard import health, remote
from upgradeguard.history import History
from upgradeguard.runner import run_upgrade_check
from upgradeguard.spec import UpgradeSpec, load_policy, new_run_id, validate_python_name, validate_spec
from upgradeguard.util import read_json

RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")
TEXT_SUFFIXES = (".json", ".txt", ".log", ".html", ".xml", ".md")
PYTHON_CHOICES = ["python3"]
SERVER_MESSAGES = {
    "connection": "The server could not be reached. Check its address, the key and the known hosts entry.",
    "preflight": "The server answered but is not suitable (it needs a recent Python and enough free disk).",
    "timeout": "The check ran longer than the time limit and was stopped.",
    "cancelled": "The check was cancelled.",
    "output": "The server returned results that did not pass the checks, so they were thrown away.",
    "worker": "The worker on the server could not finish the job.",
}


def default_repo_bases():
    bases = [os.path.realpath(os.path.join(PROJECT_ROOT, "examples"))]
    if os.environ.get("UPGRADEGUARD_REPO_BASE"):
        bases.append(os.path.realpath(os.environ["UPGRADEGUARD_REPO_BASE"]))
    return bases


@dataclass
class Settings:
    project_root: str = PROJECT_ROOT
    evidence_root: str = os.path.join(PROJECT_ROOT, "evidence")
    work_root: str = os.path.join(PROJECT_ROOT, "work")
    policy_dir: str = os.path.join(PROJECT_ROOT, "policies")
    log_path: str = os.path.join(PROJECT_ROOT, "logs", "audit.log")
    repo_bases: list = field(default_factory=default_repo_bases)
    access_token: str = os.environ.get("UPGRADEGUARD_ACCESS_TOKEN", "")
    secret: str = os.environ.get("UPGRADEGUARD_SECRET", "") or secrets.token_hex(32)
    secure_cookies: bool = os.environ.get("UPGRADEGUARD_HTTPS") == "1"
    max_active_runs: int = 2
    runs_per_hour: int = 6
    requests_per_minute: int = 120
    logins_per_minute: int = 8
    run_check: object = run_upgrade_check
    run_remote: object = remote.run_remote
    history_path: str = os.path.join(PROJECT_ROOT, "data", "history.db")
    remote_profiles_path: str = os.environ.get("UPGRADEGUARD_REMOTE_PROFILES", "")
    lookup_metadata: object = health.fetch_pypi
    checks_per_hour: int = 20


def inside(candidate, base):
    return candidate == base or candidate.startswith(base + os.sep)


def create_app(settings=None):
    settings = settings or Settings()
    if os.environ.get("UPGRADEGUARD_REQUIRE_TOKEN") == "1" and not settings.access_token:
        raise RuntimeError("UPGRADEGUARD_ACCESS_TOKEN must be set for this deployment")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024
    app.config["DEBUG"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False

    gate = security.AccessGate(settings.access_token, settings.secret)
    page_limiter = security.RateLimiter(settings.requests_per_minute, 60)
    login_limiter = security.RateLimiter(settings.logins_per_minute, 60)
    run_limiter = security.RateLimiter(settings.runs_per_hour, 3600)
    active_runs = {}
    runs_lock = threading.Lock()
    audit = build_audit_log(settings.log_path)
    history = History(settings.history_path)
    profiles = remote.load_profiles(settings.remote_profiles_path)
    health_limiter = security.RateLimiter(settings.checks_per_hour, 3600)
    cancel_flags = {}
    connection_tests = {}

    def safe_repo_path(value):
        if not value:
            return ""
        candidate = os.path.realpath(os.path.join(settings.project_root, value))
        if not os.path.isdir(candidate):
            return ""
        return candidate if any(inside(candidate, base) for base in settings.repo_bases) else ""

    def safe_evidence_dir(run_id):
        if not run_id or not RUN_ID_PATTERN.fullmatch(run_id):
            return ""
        root = os.path.realpath(settings.evidence_root)
        candidate = os.path.realpath(os.path.join(root, run_id))
        if candidate == root or not inside(candidate, root):
            return ""
        return candidate

    def policy_choices():
        if not os.path.isdir(settings.policy_dir):
            return []
        return sorted(name for name in os.listdir(settings.policy_dir) if name.endswith(".json"))

    def stored_runs():
        if not os.path.isdir(settings.evidence_root):
            return []
        rows = []
        for name in sorted(os.listdir(settings.evidence_root), reverse=True)[:200]:
            directory = os.path.join(settings.evidence_root, name)
            verdict_path = os.path.join(directory, "verdict.json")
            spec_path = os.path.join(directory, "run.json")
            if not RUN_ID_PATTERN.fullmatch(name) or not os.path.isfile(verdict_path) or not os.path.isfile(spec_path):
                continue
            verdict = read_json(verdict_path)
            spec = read_json(spec_path)
            rows.append({
                "run_id": name,
                "decision": verdict["decision"],
                "package": spec["package"],
                "from_version": spec["from_version"],
                "to_version": spec["to_version"],
                "repo": os.path.basename(spec["repo_path"].rstrip("/")),
            })
        return rows

    def merged_runs():
        with runs_lock:
            pending = [dict(item) for item in active_runs.values() if item["state"] not in ("finished", "failed")]
        return pending + stored_runs()

    def active_count():
        with runs_lock:
            return len([item for item in active_runs.values() if item["state"] in ("queued", "running")])

    def backfill_history():
        for item in stored_runs():
            if not history.has_run(item["run_id"]):
                history.add("upgrade", "%s %s to %s" % (item["package"], item["from_version"], item["to_version"]), item["decision"], item, run_id=item["run_id"])

    backfill_history()

    def start_run(spec, policy, strict_licences, location="local"):
        cancel_flags[spec.run_id] = threading.Event()
        with runs_lock:
            active_runs[spec.run_id] = {
                "run_id": spec.run_id,
                "state": "queued",
                "message": "waiting to start",
                "decision": "",
                "package": spec.package,
                "from_version": spec.from_version,
                "to_version": spec.to_version,
                "repo": os.path.basename(spec.repo_path.rstrip("/")),
                "error": "",
                "location": location,
                "log": [],
            }

        def report(message):
            with runs_lock:
                active_runs[spec.run_id]["state"] = "running"
                active_runs[spec.run_id]["message"] = message
                log = active_runs[spec.run_id]["log"]
                if not log or log[-1] != message:
                    log.append(message)
                    del log[:-60]

        def work():
            try:
                if location == "local":
                    bundle = settings.run_check(
                        spec, policy,
                        evidence_root=settings.evidence_root,
                        work_root=settings.work_root,
                        strict_licences=strict_licences,
                        progress=report,
                    )
                else:
                    bundle, _ = settings.run_remote(spec, policy, profiles[location], settings.evidence_root, progress=report,
                                                    cancelled=cancel_flags[spec.run_id].is_set, options={"strict_licences": strict_licences})
                with runs_lock:
                    active_runs[spec.run_id]["state"] = "finished"
                    active_runs[spec.run_id]["decision"] = bundle["verdict"]["decision"]
                    active_runs[spec.run_id]["message"] = "done"
                history.add("upgrade", "%s %s to %s" % (spec.package, spec.from_version, spec.to_version), bundle["verdict"]["decision"],
                            {"run_id": spec.run_id, "location": location}, run_id=spec.run_id)
            except Exception as failure:
                audit.error("run %s failed: %r", spec.run_id, failure)
                kind = getattr(failure, "kind", "")
                with runs_lock:
                    active_runs[spec.run_id]["state"] = "failed"
                    active_runs[spec.run_id]["message"] = "could not finish"
                    active_runs[spec.run_id]["kind"] = kind
                    active_runs[spec.run_id]["error"] = (
                        "%s This says nothing about the upgrade. The details are in the server log." % SERVER_MESSAGES[kind]
                        if kind in SERVER_MESSAGES
                        else "The check could not finish. The details are in the server log.")
                history.add("upgrade", "%s %s to %s" % (spec.package, spec.from_version, spec.to_version), "Not finished",
                            {"run_id": spec.run_id, "location": location, "kind": kind}, run_id=None)
            finally:
                shutil.rmtree(os.path.join(settings.work_root, spec.run_id), ignore_errors=True)
                cancel_flags.pop(spec.run_id, None)

        threading.Thread(target=work, daemon=True).start()

    def client():
        return request.remote_addr or "unknown"

    def authenticated():
        return not gate.enabled or gate.session_is_valid(request.cookies.get(security.SESSION_COOKIE))

    def csrf_ok():
        return security.same_origin(request.headers) and security.csrf_matches(
            request.cookies.get(security.CSRF_COOKIE), request.form.get("csrf"))

    def page(template, status=200, **values):
        token = request.cookies.get(security.CSRF_COOKIE) or security.new_csrf_token()
        response = make_response(render_template(template, csrf=token, authed=authenticated(), **values), status)
        response.set_cookie(security.CSRF_COOKIE, token, httponly=True, samesite="Strict", secure=settings.secure_cookies)
        return response

    def index_page(status=200, **values):
        runs = merged_runs() if authenticated() else []
        return page("index.html", status, runs=runs, policies=policy_choices(), pythons=PYTHON_CHOICES, locations=sorted(profiles),
                    login_needed=not authenticated(), **values)

    @app.before_request
    def guard():
        if request.endpoint == "health_check":
            request.max_content_length = health.MAX_BYTES + 20 * 1024
        if not page_limiter.allow(client()):
            audit.warning("%s rate limited", client())
            abort(429)
        if request.method == "POST" and not csrf_ok():
            audit.warning("%s csrf rejected on %s", client(), request.path)
            abort(403)
        if request.endpoint in ("static", "index", "login"):
            return None
        if not authenticated():
            abort(401)
        return None

    @app.after_request
    def finish(response):
        return security.add_security_headers(response, is_report=request.endpoint == "run_report")

    @app.route("/")
    def index():
        return index_page()

    @app.route("/login", methods=["POST"])
    def login():
        if not login_limiter.allow(client()):
            audit.warning("%s login rate limited", client())
            abort(429)
        if not gate.token_is_valid(request.form.get("token", "")):
            audit.warning("%s login failed", client())
            return index_page(400, error="That access token is not right.")
        audit.info("%s logged in", client())
        response = redirect(url_for("index"))
        response.set_cookie(security.SESSION_COOKIE, gate.make_session(), httponly=True, samesite="Strict",
                            secure=settings.secure_cookies, max_age=security.SESSION_SECONDS)
        return response

    @app.route("/runs", methods=["POST"])
    def create_run():
        repo = request.form.get("repo", "").strip()
        package = request.form.get("package", "").strip()
        from_version = request.form.get("from_version", "").strip()
        to_version = request.form.get("to_version", "").strip()
        python_name = request.form.get("python", "python3").strip()
        policy_name = os.path.basename(request.form.get("policy", "default.json"))
        strict = request.form.get("strict") == "on"
        location = request.form.get("location", "local")
        if location != "local" and location not in profiles:
            return index_page(400, error="That server is not set up here.")

        if not repo or not package or not from_version or not to_version:
            return index_page(400, error="Fill in the repository, the package and both versions.")
        repo_path = safe_repo_path(repo)
        if not repo_path:
            return index_page(400, error="That folder is not one this site is allowed to check. Use a project inside examples/.")
        if policy_name not in policy_choices():
            policy_name = "default.json"

        spec = UpgradeSpec(repo_path=repo_path, package=package, from_version=from_version, to_version=to_version,
                           python_bin=python_name, policy_path=os.path.join(settings.policy_dir, policy_name))
        try:
            validate_spec(spec)
            validate_python_name(python_name)
        except ValueError as problem:
            return index_page(400, error=str(problem).capitalize() + ".")

        if active_count() >= settings.max_active_runs:
            return index_page(429, error="The site is busy with other checks. Try again in a few minutes.")
        if not run_limiter.allow(client()):
            audit.warning("%s run quota used up", client())
            return index_page(429, error="That is the limit of checks per hour. Try again later.")

        spec.run_id = new_run_id(spec)
        policy = load_policy(spec.policy_path if os.path.isfile(spec.policy_path) else "")
        audit.info("%s started %s", client(), spec.run_id)
        start_run(spec, policy, strict, location)
        return redirect(url_for("show_run", run_id=spec.run_id))

    @app.route("/runs/<run_id>")
    def show_run(run_id):
        directory = safe_evidence_dir(run_id)
        if not directory:
            abort(404)
        bundle_path = os.path.join(directory, "bundle.json")
        if os.path.isfile(bundle_path):
            return page("run.html", run_id=run_id, bundle=read_json(bundle_path), pending=None)
        with runs_lock:
            pending = dict(active_runs.get(run_id, {}))
        if not pending:
            abort(404)
        return page("run.html", run_id=run_id, bundle=None, pending=pending)

    @app.route("/runs/<run_id>/state")
    def run_state(run_id):
        if not RUN_ID_PATTERN.fullmatch(run_id):
            abort(404)
        with runs_lock:
            pending = dict(active_runs.get(run_id, {}))
        if pending:
            return {"run_id": run_id, "state": pending["state"], "message": pending["message"], "log": pending.get("log", []), "error": pending.get("error", "")}
        directory = safe_evidence_dir(run_id)
        if directory and os.path.isfile(os.path.join(directory, "verdict.json")):
            return {"run_id": run_id, "state": "finished", "message": "done"}
        return {"run_id": run_id, "state": "unknown", "message": ""}

    @app.route("/runs/<run_id>/report")
    def run_report(run_id):
        directory = safe_evidence_dir(run_id)
        if not directory:
            abort(404)
        path = os.path.join(directory, "report.html")
        if not os.path.isfile(path):
            abort(404)
        return send_file(path, mimetype="text/html")

    @app.route("/runs/<run_id>/evidence.zip")
    def run_evidence(run_id):
        directory = safe_evidence_dir(run_id)
        if not directory or not os.path.isdir(directory):
            abort(404)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for root, _, files in os.walk(directory):
                for name in files:
                    full = os.path.join(root, name)
                    archive.writestr(os.path.join(run_id, os.path.relpath(full, directory)),
                                     without_host_paths(full, settings.project_root))
        buffer.seek(0)
        return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name="%s-evidence.zip" % run_id)

    @app.route("/health", methods=["POST"])
    def health_check():
        if not health_limiter.allow(client()):
            audit.warning("%s health quota used up", client())
            return index_page(429, error="That is the limit of dependency checks per hour. Try again later.", tab="health")
        upload = request.files.get("file")
        text = request.form.get("text", "")
        if upload and upload.filename:
            raw = upload.read(health.MAX_BYTES + 1)
        else:
            raw = text.encode("utf8", "replace")
        if not raw.strip():
            return index_page(400, error="Choose a requirements.txt file or paste its text.", tab="health")
        try:
            decoded = raw.decode("utf8")
            policy_name = os.path.basename(request.form.get("policy", "default.json"))
            if policy_name not in policy_choices():
                policy_name = "default.json"
            policy_path = os.path.join(settings.policy_dir, policy_name)
            report = health.analyse(decoded, load_policy(policy_path if os.path.isfile(policy_path) else ""), settings.lookup_metadata)
        except UnicodeDecodeError:
            return index_page(400, error="That file is not plain text.", tab="health")
        except health.BadFile as problem:
            return index_page(400, error="That file cannot be checked: %s." % problem, tab="health")
        label = (upload.filename if upload and upload.filename else "pasted text")[:80]
        record_id = history.add("health", label, "%d/100 %s" % (report["score"], report["status"]), report)
        audit.info("%s health check %d", client(), record_id)
        return redirect(url_for("show_health", record_id=record_id))

    @app.route("/health/<int:record_id>")
    def show_health(record_id):
        record = history.get(record_id)
        if not record or record["kind"] != "health":
            abort(404)
        return page("health.html", record=record, report=record["payload"])

    @app.route("/history")
    def history_page():
        return page("history.html", rows=history.recent(100))

    @app.route("/settings")
    def settings_page():
        shown = [{"name": item.name, "host": item.host, "user": item.user, "port": item.port, "timeout": item.timeout_seconds} for item in profiles.values()]
        return page("settings.html", profiles=sorted(shown, key=lambda item: item["name"]), tests=dict(connection_tests))

    @app.route("/settings/test", methods=["POST"])
    def settings_test():
        name = request.form.get("profile", "")
        if name not in profiles:
            abort(404)
        if not run_limiter.allow(client()):
            abort(429)
        try:
            caps = remote.test_connection(profiles[name])
            outcome = "Connected. Python %s, %d MB free." % (caps["python"], caps["disk_free_mb"])
        except remote.RemoteError as problem:
            audit.warning("%s test of profile %s failed (%s): %s", client(), name, problem.kind, str(problem)[:300])
            outcome = SERVER_MESSAGES.get(problem.kind, "The test failed. The details are in the server log.")
        connection_tests[name] = outcome
        audit.info("%s tested profile %s", client(), name)
        return redirect(url_for("settings_page"))

    @app.route("/runs/<run_id>/cancel", methods=["POST"])
    def cancel_run(run_id):
        if not RUN_ID_PATTERN.fullmatch(run_id):
            abort(404)
        flag = cancel_flags.get(run_id)
        with runs_lock:
            known = run_id in active_runs and active_runs[run_id].get("location", "local") != "local"
        if not flag or not known:
            abort(404)
        flag.set()
        audit.info("%s cancelled %s", client(), run_id)
        return redirect(url_for("show_run", run_id=run_id))

    @app.errorhandler(Exception)
    def any_problem(problem):
        status = getattr(problem, "code", 500)
        if not isinstance(status, int) or status < 400:
            status = 500
        if status >= 500:
            audit.error("unhandled error: %r", problem)
        messages = {400: "That request was not understood.", 401: "Log in on the first page to use this site.",
                    403: "That request was refused.", 404: "There is nothing here.", 413: "That request was too large.",
                    429: "Too many requests. Slow down and try again soon."}
        return page("error.html", status, code=status, message=messages.get(status, "Something went wrong on our side."))

    return app


def without_host_paths(path, project_root):
    with open(path, "rb") as handle:
        data = handle.read()
    if not path.endswith(TEXT_SUFFIXES):
        return data
    return data.replace(project_root.encode(), b"<project>").replace(os.path.expanduser("~").encode(), b"<home>")


def build_audit_log(path):
    logger = logging.getLogger("upgradeguard.audit.%s" % path)
    if not logger.handlers:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def run_server():
    host = os.environ.get("HOST", "127.0.0.1")
    settings = Settings()
    if not security.is_loopback(host) and not settings.access_token:
        sys.exit("Refusing to listen on %s without UPGRADEGUARD_ACCESS_TOKEN set." % host)
    create_app(settings).run(host=host, port=int(os.environ.get("PORT", "5057")), debug=False)


if __name__ == "__main__":
    run_server()
else:
    app = create_app()
