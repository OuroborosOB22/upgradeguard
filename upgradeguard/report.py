import html
import os

from .util import write_text

VERDICT_COLOURS = {
    "Accept": ("#1a7f37", "#dafbe1"),
    "Reject": ("#cf222e", "#ffebe9"),
    "Insufficient Evidence": ("#9a6700", "#fff8c5"),
}


def esc(value):
    return html.escape(str(value if value is not None else ""))


def write_report(bundle, path):
    write_text(path, render_report(bundle))
    return path


def render_report(bundle):
    verdict = bundle["verdict"]
    spec = bundle["spec"]
    colour, background = VERDICT_COLOURS.get(verdict["decision"], ("#57606a", "#f6f8fa"))

    sections = [
        render_header(bundle, verdict, colour, background),
        render_reasons(verdict),
        render_environments(bundle),
        render_dependency_diff(bundle),
        render_tests(bundle),
        render_conflicts(bundle),
        render_vulnerabilities(bundle),
        render_licenses(bundle),
        render_evidence_index(bundle),
    ]

    return TEMPLATE % {
        "title": esc("UpgradeGuard report %s" % bundle["run_id"]),
        "body": "\n".join(sections),
    }


def render_header(bundle, verdict, colour, background):
    spec = bundle["spec"]
    return """
<header class="head">
  <div class="badge" style="color:%s;background:%s;border-color:%s">%s</div>
  <h1>%s %s to %s</h1>
  <p class="sub">repository <code>%s</code> | run <code>%s</code> | interpreter <code>%s</code> | %ss</p>
</header>
""" % (
        colour, background, colour, esc(verdict["decision"]),
        esc(spec["package"]), esc(spec["from_version"]), esc(spec["to_version"]),
        esc(spec["repo_path"]), esc(bundle["run_id"]), esc(bundle["python_bin"]),
        esc(bundle["total_seconds"]),
    )


def render_reasons(verdict):
    rows = []
    for item in verdict["reasons"] + verdict["notes"]:
        evidence = " ".join("<code>%s</code>" % esc(name) for name in item["evidence"])
        rows.append(
            "<li class=\"reason %s\"><span class=\"code\">%s</span><p>%s</p><p class=\"ev\">evidence: %s</p></li>"
            % (esc(item["severity"]), esc(item["code"]), esc(item["message"]), evidence)
        )
    return section("Why this verdict", "<ul class=\"reasons\">%s</ul>" % "".join(rows))


def render_environments(bundle):
    rows = []
    for side in ("before", "after"):
        build = bundle[side]["build"]
        state = "built" if build["ok"] else "failed at %s" % (build["failure_stage"] or "unknown stage")
        rows.append(row([
            side, state, str(len(build["freeze"])), "%ss" % build["duration"],
            "<code>%s/install.log</code>" % side,
        ]))
    body = table(["environment", "result", "packages installed", "build time", "log"], rows)
    failure = ""
    for side in ("before", "after"):
        build = bundle[side]["build"]
        if not build["ok"] and build["failure_output"]:
            failure += "<h3>%s environment output</h3><pre>%s</pre>" % (esc(side), esc(build["failure_output"]))
    return section("Environment builds", body + failure)


def render_dependency_diff(bundle):
    diff = bundle["diff"]["graph"]
    rows = []
    for item in diff["changed"]:
        rows.append(row([item["name"], item["from_version"], item["to_version"],
                         "direct" if item["direct"] else "transitive", "version changed"]))
    for item in diff["added"]:
        rows.append(row([item["name"], "not present", item["version"],
                         "direct" if item["direct"] else "transitive", "added"]))
    for item in diff["removed"]:
        rows.append(row([item["name"], item["version"], "not present",
                         "direct" if item["direct"] else "transitive", "removed"]))
    if not rows:
        rows.append(row(["no package changed", "", "", "", ""]))
    summary = "<p class=\"sub\">%d packages before, %d after, %d unchanged.</p>" % (
        diff["before_total"], diff["after_total"], diff["unchanged_count"])
    return section("Dependency graph diff", summary + table(
        ["package", "before", "after", "kind", "change"], rows))


def render_tests(bundle):
    diff = bundle["diff"]["tests"]
    before = bundle["before"]["tests"]
    after = bundle["after"]["tests"]
    counts = table(
        ["environment", "passed", "failed", "error", "skipped", "total", "time"],
        [
            row(["before", before["counts"].get("passed", 0), before["counts"].get("failed", 0),
                 before["counts"].get("error", 0), before["counts"].get("skipped", 0),
                 before["counts"].get("total", 0), "%ss" % before["duration"]]),
            row(["after", after["counts"].get("passed", 0), after["counts"].get("failed", 0),
                 after["counts"].get("error", 0), after["counts"].get("skipped", 0),
                 after["counts"].get("total", 0), "%ss" % after["duration"]]),
        ],
    )
    if diff["regressions"]:
        rows = [row([item["test"], item["before"], item["after"], item["message"]]) for item in diff["regressions"]]
        regressions = "<h3>Regressions</h3>" + table(["test", "before", "after", "message"], rows)
    else:
        regressions = "<h3>Regressions</h3><p class=\"ok\">No test passed before and failed after.</p>"

    tail = ""
    if after["tail"]:
        tail = "<h3>Test output from the upgraded environment</h3><pre>%s</pre>" % esc(after["tail"])
    return section("Test suite", counts + regressions + tail)


def render_conflicts(bundle):
    diff = bundle["diff"]["conflicts"]
    if not diff["introduced"] and not diff["unchanged"]:
        return section("Dependency conflicts", "<p class=\"ok\">pip check reported no broken requirements in either environment.</p>")
    parts = []
    if diff["introduced"]:
        parts.append("<h3>New after the upgrade</h3><pre>%s</pre>" % esc("\n".join(diff["introduced"])))
    if diff["unchanged"]:
        parts.append("<h3>Present in both</h3><pre>%s</pre>" % esc("\n".join(diff["unchanged"])))
    if diff["resolved"]:
        parts.append("<h3>Fixed by the upgrade</h3><pre>%s</pre>" % esc("\n".join(diff["resolved"])))
    return section("Dependency conflicts", "".join(parts))


def render_vulnerabilities(bundle):
    diff = bundle["diff"]["vulnerabilities"]
    source = bundle["after"]["vulnerabilities"]["source"]
    parts = ["<p class=\"sub\">source: %s | %d finding(s) before, %d after</p>" % (
        esc(source), diff["before_count"], diff["after_count"])]
    parts.append(vulnerability_table("Introduced by the upgrade", diff["introduced"]))
    parts.append(vulnerability_table("Fixed by the upgrade", diff["resolved"]))
    parts.append(vulnerability_table("Still present", diff["remaining"]))
    return section("Known vulnerabilities", "".join(parts))


def vulnerability_table(heading, findings):
    if not findings:
        return "<h3>%s</h3><p class=\"ok\">none</p>" % esc(heading)
    rows = [row([item["package"], item["version"], item["id"],
                 ", ".join(item["fix_versions"]) or "no fix listed", item["summary"]])
            for item in findings]
    return "<h3>%s</h3>" % esc(heading) + table(
        ["package", "version", "advisory", "fixed in", "summary"], rows)


def render_licenses(bundle):
    after = bundle["after"]["licenses"]
    diff = bundle["diff"]["licenses"]
    parts = ["<p class=\"sub\">policy <code>%s</code> | %d package(s) allowed | %d denied | %d unrecognised</p>" % (
        esc(after["policy"]), after["allowed_count"], len(after["violations"]), len(after["unknown"]))]
    if diff["introduced"]:
        rows = [row([item["package"], item["version"], item["canonical"], item["license_raw"], item["rule"]])
                for item in diff["introduced"]]
        parts.append("<h3>New policy violations</h3>" + table(
            ["package", "version", "licence", "declared as", "rule"], rows))
    else:
        parts.append("<h3>New policy violations</h3><p class=\"ok\">none</p>")
    if after["violations"]:
        rows = [row([item["package"], item["version"], item["canonical"], item["license_raw"]])
                for item in after["violations"]]
        parts.append("<h3>All denied packages after the upgrade</h3>" + table(
            ["package", "version", "licence", "declared as"], rows))
    return section("Licence policy", "".join(parts))


def render_evidence_index(bundle):
    files = [
        "run.json", "policy.json", "diff.json", "verdict.json", "bundle.json",
        "before/install.log", "before/requirements.used.txt", "before/freeze.txt",
        "before/graph.json", "before/conflicts.txt", "before/licenses.json",
        "before/audit.json", "before/junit.xml", "before/pytest.log",
        "after/install.log", "after/requirements.used.txt", "after/freeze.txt",
        "after/graph.json", "after/conflicts.txt", "after/licenses.json",
        "after/audit.json", "after/junit.xml", "after/pytest.log",
    ]
    present = [name for name in files if os.path.isfile(os.path.join(bundle["evidence_dir"], name))]
    items = "".join("<li><code>%s</code></li>" % esc(name) for name in present)
    return section("Evidence files", "<p class=\"sub\">stored under <code>%s</code></p><ul class=\"files\">%s</ul>" % (
        esc(bundle["evidence_dir"]), items))


def section(title, body):
    return "<section><h2>%s</h2>%s</section>" % (esc(title), body)


def table(headers, rows):
    head = "".join("<th>%s</th>" % esc(item) for item in headers)
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (head, "".join(rows))


def row(cells):
    return "<tr>%s</tr>" % "".join("<td>%s</td>" % esc(cell) for cell in cells)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<style>
:root { color-scheme: light; }
body { margin:0; padding:32px; background:#f6f8fa; color:#1f2328;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; line-height:1.5; }
.head { max-width:1000px; margin:0 auto 24px; }
h1 { font-size:24px; margin:12px 0 4px; }
h2 { font-size:18px; margin:0 0 12px; }
h3 { font-size:14px; margin:20px 0 8px; text-transform:uppercase; letter-spacing:.04em; color:#57606a; }
.badge { display:inline-block; padding:6px 14px; border-radius:999px; border:1px solid;
  font-weight:600; font-size:13px; }
.sub { color:#57606a; font-size:13px; margin:4px 0 0; }
section { max-width:1000px; margin:0 auto 20px; background:#fff; border:1px solid #d1d9e0;
  border-radius:8px; padding:20px; overflow-x:auto; }
table { border-collapse:collapse; width:100%%; font-size:13px; }
th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #d1d9e0; vertical-align:top; }
th { background:#f6f8fa; font-weight:600; }
code { background:#eff2f5; padding:1px 5px; border-radius:4px; font-size:12px; }
pre { background:#0d1117; color:#e6edf3; padding:14px; border-radius:6px; overflow-x:auto;
  font-size:12px; white-space:pre-wrap; }
ul.reasons { list-style:none; padding:0; margin:0; }
ul.reasons li { border-left:3px solid #57606a; padding:4px 0 4px 14px; margin-bottom:14px; }
ul.reasons li.blocking { border-color:#cf222e; }
ul.reasons li.warning { border-color:#9a6700; }
ul.reasons li.info { border-color:#1a7f37; }
.code { font-family:ui-monospace,monospace; font-size:12px; color:#57606a; }
.ev { font-size:12px; color:#57606a; margin:4px 0 0; }
.ok { color:#1a7f37; font-size:13px; }
ul.files { columns:2; font-size:12px; }
</style>
</head>
<body>
%(body)s
</body>
</html>
"""
