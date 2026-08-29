ACCEPT = "Accept"
REJECT = "Reject"
INSUFFICIENT = "Insufficient Evidence"


def reason(code, message, evidence, severity="blocking"):
    return {"code": code, "message": message, "evidence": evidence, "severity": severity}


def decide(bundle):
    before_build = bundle["before"]["build"]
    after_build = bundle["after"]["build"]
    before_tests = bundle["before"]["tests"]
    after_tests = bundle["after"]["tests"]

    reasons = []
    notes = []

    if not before_build["ok"]:
        reasons.append(reason(
            "baseline-build-failed",
            "The environment for the current version could not be built, so there is nothing to compare against. Stage that failed: %s." % before_build["failure_stage"],
            ["before/install.log", "before/requirements.used.txt"],
        ))
        return finalise(INSUFFICIENT, reasons, notes, bundle)

    if not after_build["ok"]:
        reasons.append(reason(
            "upgrade-build-failed",
            "The environment for the proposed version could not be built. Stage that failed: %s." % after_build["failure_stage"],
            ["after/install.log", "after/requirements.used.txt"],
        ))
        return finalise(REJECT, reasons, notes, bundle)

    if not before_tests["ran"] or not after_tests["ran"]:
        reasons.append(reason(
            "tests-did-not-run",
            "The test suite could not be collected in at least one environment, so a regression cannot be proved either way.",
            ["before/pytest.log", "after/pytest.log"],
        ))
        return finalise(INSUFFICIENT, reasons, notes, bundle)

    conflicts = bundle["diff"]["conflicts"]["introduced"]
    if conflicts:
        reasons.append(reason(
            "new-dependency-conflict",
            "The upgrade introduces %d dependency conflict(s) reported by pip check: %s" % (len(conflicts), "; ".join(conflicts[:3])),
            ["after/conflicts.txt", "after/pip-check.log"],
        ))

    introduced_vulns = bundle["diff"]["vulnerabilities"]["introduced"]
    if introduced_vulns:
        listed = ", ".join("%s in %s" % (item["id"], item["package"]) for item in introduced_vulns[:3])
        reasons.append(reason(
            "new-vulnerability",
            "The upgrade brings in %d known vulnerability finding(s) that were not present before: %s" % (len(introduced_vulns), listed),
            ["after/audit.json"],
        ))

    strict_licences = bundle.get("options", {}).get("strict_licences", False)
    existing_violations = bundle["after"]["licenses"]["violations"]
    licence_violations = bundle["diff"]["licenses"]["introduced"]
    if licence_violations:
        listed = ", ".join("%s (%s)" % (item["package"], item["canonical"]) for item in licence_violations[:3])
        reasons.append(reason(
            "licence-policy-violation",
            "The upgrade adds %d package(s) that the licence policy denies: %s" % (len(licence_violations), listed),
            ["after/licenses.json", "policy.json"],
        ))

    carried_over = [item for item in existing_violations
                    if item["package"] not in {entry["package"] for entry in licence_violations}]
    if carried_over:
        listed = ", ".join("%s (%s)" % (item["package"], item["canonical"]) for item in carried_over[:3])
        message = "%d package(s) already breached the licence policy before the upgrade: %s" % (len(carried_over), listed)
        if strict_licences:
            reasons.append(reason("licence-policy-precondition", message + " Strict licence mode treats this as blocking.",
                                  ["after/licenses.json", "policy.json"]))
        else:
            notes.append(reason("licence-policy-precondition", message + " The upgrade did not cause this, so it does not block the verdict.",
                                ["after/licenses.json", "policy.json"], severity="warning"))

    regressions = bundle["diff"]["tests"]["regressions"]
    if regressions:
        listed = ", ".join(item["test"] for item in regressions[:3])
        reasons.append(reason(
            "test-regression",
            "%d test(s) passed before the upgrade and fail after it: %s" % (len(regressions), listed),
            ["before/junit.xml", "after/junit.xml", "after/pytest.log"],
        ))

    new_failing = bundle["diff"]["tests"]["new_failing_tests"]
    if new_failing:
        notes.append(reason(
            "new-failing-tests",
            "%d test(s) exist only in the upgraded run and are failing there." % len(new_failing),
            ["after/junit.xml"],
            severity="warning",
        ))

    resolved_vulns = bundle["diff"]["vulnerabilities"]["resolved"]
    if resolved_vulns:
        notes.append(reason(
            "vulnerabilities-resolved",
            "The upgrade removes %d known vulnerability finding(s)." % len(resolved_vulns),
            ["before/audit.json", "after/audit.json"],
            severity="info",
        ))

    resolved_licences = bundle["diff"]["licenses"]["resolved"]
    if resolved_licences:
        listed = ", ".join("%s (%s)" % (item["package"], item["canonical"]) for item in resolved_licences[:3])
        notes.append(reason(
            "licence-violations-resolved",
            "The upgrade removes %d package(s) that the licence policy denied: %s" % (len(resolved_licences), listed),
            ["before/licenses.json", "after/licenses.json"],
            severity="info",
        ))

    unknown_licences = bundle["diff"]["licenses"]["new_unknown"]
    if unknown_licences:
        notes.append(reason(
            "unidentified-licence",
            "%d newly added package(s) have a licence the policy does not recognise." % len(unknown_licences),
            ["after/licenses.json"],
            severity="warning",
        ))

    if reasons:
        return finalise(REJECT, reasons, notes, bundle)

    reasons.append(reason(
        "no-blocking-evidence",
        "Both environments built, the test suite ran in both, and no new conflict, vulnerability, licence violation or test regression was found.",
        ["diff.json", "before/freeze.txt", "after/freeze.txt"],
        severity="info",
    ))
    return finalise(ACCEPT, reasons, notes, bundle)


def finalise(decision, reasons, notes, bundle):
    return {
        "decision": decision,
        "reasons": reasons,
        "notes": notes,
        "headline": headline_for(decision, bundle),
    }


def headline_for(decision, bundle):
    spec = bundle["spec"]
    return "%s: upgrading %s from %s to %s" % (
        decision, spec["package"], spec["from_version"], spec["to_version"],
    )
