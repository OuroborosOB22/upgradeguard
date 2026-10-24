from upgradeguard.checks.licenses import check_licenses, diff_licenses, evaluate_package, normalise_license, split_expression
from upgradeguard.spec import LicencePolicy, load_policy


def test_known_licence_texts_are_normalised():
    assert normalise_license("MIT License") == "MIT"
    assert normalise_license("Apache Software License") == "APACHE-2.0"
    assert normalise_license("GNU Lesser General Public License v3 (LGPLv3)") == "LGPL-3.0"
    assert normalise_license("BSD-3-Clause") == "BSD-3-CLAUSE"
    assert normalise_license("") == "UNKNOWN"
    assert normalise_license("something nobody has heard of") == "UNKNOWN"


def test_expressions_are_split_on_or_and_and():
    assert split_expression("MIT OR Apache-2.0") == ["MIT", "Apache-2.0"]
    assert split_expression("(MIT AND BSD-3-Clause)") == ["MIT", "BSD-3-Clause"]
    assert split_expression("") == []


def test_allowed_denied_and_unknown_outcomes():
    policy = load_policy("")
    assert evaluate_package("a", "MIT", policy)["status"] == "allowed"
    assert evaluate_package("a", "LGPL-2.1-or-later", policy)["status"] == "denied"
    assert evaluate_package("a", "Totally custom", policy)["status"] == "unknown"


def test_dual_licence_passes_when_one_side_is_allowed():
    assert evaluate_package("a", "GPL-3.0 OR MIT", load_policy(""))["status"] == "allowed"


def test_unknown_can_be_made_fatal():
    policy = LicencePolicy(allowed=["MIT"], unknown_action="fail")
    assert evaluate_package("a", "", policy)["status"] == "denied"


def test_package_exception_overrides_the_denied_list():
    policy = LicencePolicy(allowed=["MIT"], denied=["LGPL-2.1"], package_exceptions={"chardet": "LGPL-2.1"})
    assert evaluate_package("chardet", "LGPL-2.1", policy)["status"] == "allowed"


def graph_with(licences):
    nodes = {name: {"version": "1", "direct": True, "license_raw": raw, "license_source": "metadata"} for name, raw in licences.items()}
    return {"nodes": nodes}


def test_check_licenses_writes_report_and_lists_violations(tmp_path):
    report = check_licenses(graph_with({"a": "MIT", "b": "GPL-3.0"}), load_policy(""), str(tmp_path))
    assert [item["package"] for item in report["violations"]] == ["b"]
    assert report["allowed_count"] == 1
    assert (tmp_path / "licenses.json").exists()


def test_diff_separates_new_old_and_resolved_violations(tmp_path):
    policy = load_policy("")
    before = check_licenses(graph_with({"old": "GPL-3.0", "gone": "GPL-3.0"}), policy, str(tmp_path))
    after = check_licenses(graph_with({"old": "GPL-3.0", "new": "AGPL-3.0"}), policy, str(tmp_path))
    diff = diff_licenses(before, after)
    assert [item["package"] for item in diff["introduced"]] == ["new"]
    assert [item["package"] for item in diff["resolved"]] == ["gone"]
    assert [item["package"] for item in diff["remaining"]] == ["old"]


def test_an_and_expression_needs_every_part_to_be_allowed():
    from upgradeguard.checks.licenses import evaluate_package
    from upgradeguard.spec import load_policy
    policy = load_policy("")
    assert evaluate_package("x", "MIT AND Apache-2.0", policy)["status"] == "allowed"
    assert evaluate_package("x", "BSD-3-Clause AND 0BSD", policy)["status"] == "unknown"
    assert evaluate_package("x", "MIT AND GPL-3.0", policy)["status"] == "denied"
    assert evaluate_package("x", "GPL-3.0 OR MIT", policy)["status"] == "allowed"
