from helpers import empty_diff, make_bundle, side

from upgradeguard.baselines import (
    PIP_AUDIT, PIP_CHECK, STATIC_FILE, major_part, pinned_version, pip_audit_verdict, pip_check_verdict, static_file_verdict,
)
from upgradeguard.verdict import ACCEPT, REJECT

ADVISORIES = [{"package": "urllib3", "fixed_in": "2.0.6"}]


def test_pip_check_baseline_rejects_only_on_new_conflicts_or_failed_install():
    assert pip_check_verdict(make_bundle()) == ACCEPT
    diff = empty_diff()
    diff["conflicts"]["introduced"] = ["x"]
    assert pip_check_verdict(make_bundle(diff=diff)) == REJECT
    assert pip_check_verdict(make_bundle(after=side(build_ok=False))) == REJECT


def test_pip_check_baseline_is_blind_to_test_regressions():
    diff = empty_diff()
    diff["tests"]["regressions"] = [{"test": "t"}]
    assert pip_check_verdict(make_bundle(diff=diff)) == ACCEPT


def test_pip_audit_baseline_rejects_only_on_new_vulnerabilities():
    assert pip_audit_verdict(make_bundle()) == ACCEPT
    diff = empty_diff()
    diff["vulnerabilities"]["introduced"] = [{"id": "X"}]
    assert pip_audit_verdict(make_bundle(diff=diff)) == REJECT


def test_major_part_reads_the_leading_number():
    assert major_part("3.1.6") == 3
    assert major_part("v2.0") == 2
    assert major_part("weird") == 0


def test_static_checker_flags_major_version_jumps():
    assert static_file_verdict("jinja2", "3.0.3", "3.1.6", ADVISORIES) == ACCEPT
    assert static_file_verdict("sqlalchemy", "1.4.52", "2.0.0", ADVISORIES) == REJECT


def test_static_checker_flags_pins_below_a_known_fix():
    assert static_file_verdict("urllib3", "1.26.18", "2.0.5", ADVISORIES) == REJECT
    assert static_file_verdict("urllib3", "2.0.6", "2.0.7", ADVISORIES) == ACCEPT


def test_static_checker_ignores_other_packages_advisories():
    assert static_file_verdict("requests", "2.0.0", "2.1.0", ADVISORIES) == ACCEPT


def test_pinned_version_reads_the_requirements_file(tmp_path):
    path = tmp_path / "req.txt"
    path.write_text("# c\nRequests[socks]==2.32.5 ; python_version > '3'\nflask>=3\n")
    assert pinned_version(str(path), "requests") == "2.32.5"
    assert pinned_version(str(path), "flask") == ""
    assert pinned_version(str(path), "absent") == ""


def test_baseline_names_are_stable():
    assert (PIP_CHECK, PIP_AUDIT, STATIC_FILE) == ("pip-check", "pip-audit", "static-file")
