METHOD_LABELS = {
    "upgradeguard": "UpgradeGuard",
    "pip-check": "pip check only",
    "pip-audit": "pip-audit only",
    "static-file": "static file check only",
}


def percent(value):
    return "n/a" if value is None else "%.1f%%" % (value * 100)


def methods_table(methods):
    lines = ["| method | accuracy | precision | recall | false approvals | false rejections | inconclusive |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for key, label in METHOD_LABELS.items():
        if key not in methods:
            continue
        item = methods[key]
        lines.append("| %s | %s | %s | %s | %d | %d | %d |" % (
            label, percent(item["accuracy"]), percent(item["precision"]), percent(item["recall"]),
            item["false_approvals"], item["false_rejections"], item["inconclusive"]))
    return lines


def signals_table(signals):
    lines = ["| signal | cases | detected | detection rate |", "| --- | --- | --- | --- |"]
    for name, item in signals.items():
        lines.append("| %s | %d | %d | %s |" % (name, item["cases"], item["detected"], percent(item["detection_rate"])))
    return lines


def cases_table(results):
    lines = ["| case | expected | actual | ok | seconds |", "| --- | --- | --- | --- | --- |"]
    for row in results:
        lines.append("| %s | %s | %s | %s | %s |" % (
            row["id"], row["expected"], row["actual"], "yes" if row["verdict_correct"] else "NO", row["seconds"]))
    return lines


def render_results(report):
    builds = report["builds"]
    timing = report["timing"]
    notes = report.get("provenance", {})
    provenance = ["Run details: " + ", ".join("%s %s" % (key.replace("_", " "), value) for key, value in sorted(notes.items())), ""] if notes else []
    lines = ["# Benchmark results", "",
             "Cases: %d. Positive class is Reject. Ground truth was committed before these results." % report["summary"]["cases"],
             ""] + provenance + ["## Verdicts against the baselines", ""]
    lines += methods_table(report["methods"])
    lines += ["", "## Detection by signal", ""] + signals_table(report["signals"])
    lines += ["", "## Environment builds", "",
              "- baseline environment built: %s" % percent(builds["baseline_build_success"]),
              "- upgraded environment built when it should: %s" % percent(builds["upgrade_build_success"]),
              "- impossible builds correctly caught: %s" % percent(builds["build_failure_detection"]),
              "", "## Execution time", "",
              "- mean %s s, median %s s, longest %s s, total %s s" % (
                  timing["mean_seconds"], timing["median_seconds"], timing["max_seconds"], timing["total_seconds"]),
              "", "## Every case", ""]
    lines += cases_table(report["results"])
    return "\n".join(lines) + "\n"


def write_results_markdown(report, path):
    with open(path, "w") as handle:
        handle.write(render_results(report))
