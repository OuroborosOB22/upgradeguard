import io
import os
import re
import sys
import threading
import zipfile

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from upgradeguard.runner import run_upgrade_check
from upgradeguard.spec import UpgradeSpec, load_policy, new_run_id
from upgradeguard.util import read_json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE_ROOT = os.path.join(PROJECT_ROOT, "evidence")
WORK_ROOT = os.path.join(PROJECT_ROOT, "work")
POLICY_DIR = os.path.join(PROJECT_ROOT, "policies")

RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")

ALLOWED_REPO_BASES = [os.path.realpath(os.path.join(PROJECT_ROOT, "examples"))]
if os.environ.get("UPGRADEGUARD_REPO_BASE"):
    ALLOWED_REPO_BASES.append(os.path.realpath(os.environ["UPGRADEGUARD_REPO_BASE"]))

app = Flask(__name__)
active_runs = {}
runs_lock = threading.Lock()


def inside(candidate, base):
    return candidate == base or candidate.startswith(base + os.sep)


def safe_repo_path(value):
    if not value:
        return ""
    candidate = os.path.realpath(os.path.join(PROJECT_ROOT, value))
    if not os.path.isdir(candidate):
        return ""
    for base in ALLOWED_REPO_BASES:
        if inside(candidate, base):
            return candidate
    return ""


def safe_evidence_dir(run_id):
    if not run_id or not RUN_ID_PATTERN.fullmatch(run_id):
        return ""
    root = os.path.realpath(EVIDENCE_ROOT)
    candidate = os.path.realpath(os.path.join(root, run_id))
    if candidate == root or not inside(candidate, root):
        return ""
    return candidate


def policy_choices():
    if not os.path.isdir(POLICY_DIR):
        return []
    return sorted(name for name in os.listdir(POLICY_DIR) if name.endswith(".json"))


def stored_runs():
    if not os.path.isdir(EVIDENCE_ROOT):
        return []
    rows = []
    for name in sorted(os.listdir(EVIDENCE_ROOT), reverse=True):
        directory = os.path.join(EVIDENCE_ROOT, name)
        verdict_path = os.path.join(directory, "verdict.json")
        spec_path = os.path.join(directory, "run.json")
        if not os.path.isfile(verdict_path) or not os.path.isfile(spec_path):
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
        pending = [dict(item) for item in active_runs.values() if item["state"] != "finished"]
    return pending + stored_runs()


def start_run(spec, policy, strict_licences):
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
        }

    def report(message):
        with runs_lock:
            active_runs[spec.run_id]["state"] = "running"
            active_runs[spec.run_id]["message"] = message

    def work():
        try:
            bundle = run_upgrade_check(
                spec, policy,
                evidence_root=EVIDENCE_ROOT,
                work_root=WORK_ROOT,
                strict_licences=strict_licences,
                progress=report,
            )
            with runs_lock:
                active_runs[spec.run_id]["state"] = "finished"
                active_runs[spec.run_id]["decision"] = bundle["verdict"]["decision"]
                active_runs[spec.run_id]["message"] = "done"
        except Exception as failure:
            with runs_lock:
                active_runs[spec.run_id]["state"] = "failed"
                active_runs[spec.run_id]["message"] = "could not finish"
                active_runs[spec.run_id]["error"] = str(failure)

    threading.Thread(target=work, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html", runs=merged_runs(), policies=policy_choices())


@app.route("/runs", methods=["POST"])
def create_run():
    repo = request.form.get("repo", "").strip()
    package = request.form.get("package", "").strip()
    from_version = request.form.get("from_version", "").strip()
    to_version = request.form.get("to_version", "").strip()
    policy_name = request.form.get("policy", "default.json")
    strict = request.form.get("strict") == "on"

    if not repo or not package or not from_version or not to_version:
        return render_template("index.html", runs=merged_runs(), policies=policy_choices(),
                               error="Fill in the repository, the package and both versions."), 400

    repo_path = safe_repo_path(repo)
    if not repo_path:
        return render_template("index.html", runs=merged_runs(), policies=policy_choices(),
                               error="That folder is not one this site is allowed to check. "
                                     "Use a project inside examples/."), 400

    policy_name = os.path.basename(policy_name)
    if policy_name not in policy_choices():
        policy_name = "default.json"

    spec = UpgradeSpec(
        repo_path=repo_path,
        package=package,
        from_version=from_version,
        to_version=to_version,
        python_bin=request.form.get("python", "python3"),
        policy_path=os.path.join(POLICY_DIR, policy_name),
    )
    spec.run_id = new_run_id(spec)
    policy = load_policy(spec.policy_path if os.path.isfile(spec.policy_path) else "")
    start_run(spec, policy, strict)
    return redirect(url_for("show_run", run_id=spec.run_id))


@app.route("/runs/<run_id>")
def show_run(run_id):
    directory = safe_evidence_dir(run_id)
    if not directory:
        abort(404)
    bundle_path = os.path.join(directory, "bundle.json")
    if os.path.isfile(bundle_path):
        return render_template("run.html", run_id=run_id, bundle=read_json(bundle_path), pending=None)
    with runs_lock:
        pending = dict(active_runs.get(run_id, {}))
    if not pending:
        abort(404)
    return render_template("run.html", run_id=run_id, bundle=None, pending=pending)


@app.route("/runs/<run_id>/state")
def run_state(run_id):
    with runs_lock:
        pending = dict(active_runs.get(run_id, {}))
    if pending:
        return pending
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
    return send_file(path)


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
                archive.write(full, os.path.join(run_id, os.path.relpath(full, directory)))
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                     download_name="%s-evidence.zip" % run_id)


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("UPGRADEGUARD_DEBUG") == "1",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5057")),
    )
