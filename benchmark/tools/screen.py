import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from upgradeguard.repos import REQUIREMENTS_NAME, load_repo_entries, repo_slug
from upgradeguard.runner import run_upgrade_check
from upgradeguard.spec import UpgradeSpec, load_policy


def screen_one(entry, evidence_root, work_root):
    package, version = entry["probe"].split("==")
    spec = UpgradeSpec(
        repo_path=os.path.join(ROOT, "benchmark", "repos", repo_slug(entry["name"])),
        package=package,
        from_version=version,
        to_version=version,
        python_bin=entry["python"],
        requirements_file=REQUIREMENTS_NAME,
        install_project=entry["install_project"],
        pytest_args=entry["pytest_args"],
        build_env=entry["env"],
        run_id="screen-%s" % repo_slug(entry["name"]),
    )
    started = time.time()
    try:
        bundle = run_upgrade_check(spec, load_policy(""), evidence_root=evidence_root, work_root=work_root)
        before = bundle["before"]
        counts = before["tests"]["counts"]
        return {
            "name": entry["name"],
            "built": before["build"]["ok"],
            "failure_stage": before["build"]["failure_stage"],
            "tests_ran": before["tests"]["ran"],
            "counts": counts,
            "verdict": bundle["verdict"]["decision"],
            "seconds": round(time.time() - started, 1),
            "evidence_dir": os.path.relpath(bundle["evidence_dir"], ROOT),
        }
    except Exception as failure:
        return {"name": entry["name"], "error": str(failure)[:300], "seconds": round(time.time() - started, 1)}


def main():
    only = set(sys.argv[1:])
    entries = [e for e in load_repo_entries(os.path.join(ROOT, "benchmark", "repos.json"))
               if e["status"] != "dropped" and (not only or e["name"] in only)]
    evidence_root = os.path.join(ROOT, "evidence", "screening")
    work_root = os.path.join(ROOT, "work", "screening")
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(lambda entry: screen_one(entry, evidence_root, work_root), entries))
    for row in rows:
        print(json.dumps(row))
    out = os.path.join(ROOT, "benchmark", "screening.json")
    previous = json.load(open(out)) if os.path.isfile(out) else {}
    previous.update({row["name"]: row for row in rows})
    json.dump(previous, open(out, "w"), indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
