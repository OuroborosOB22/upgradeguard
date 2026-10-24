from helpers import make_bundle, note_codes, reason_codes, side, empty_diff

from upgradeguard.verdict import ACCEPT, INSUFFICIENT, REJECT, decide


def test_clean_run_is_accepted():
    verdict = decide(make_bundle())
    assert verdict["decision"] == ACCEPT
    assert reason_codes(verdict) == ["no-blocking-evidence"]


def test_headline_names_the_upgrade():
    verdict = decide(make_bundle())
    assert verdict["headline"] == "Accept: upgrading requests from 2.28.2 to 2.32.5"


def test_broken_baseline_gives_insufficient_evidence():
    verdict = decide(make_bundle(before=side(build_ok=False, stage="dependency-install")))
    assert verdict["decision"] == INSUFFICIENT
    assert reason_codes(verdict) == ["baseline-build-failed"]


def test_broken_upgrade_build_is_rejected():
    verdict = decide(make_bundle(after=side(build_ok=False, stage="dependency-install")))
    assert verdict["decision"] == REJECT
    assert reason_codes(verdict) == ["upgrade-build-failed"]


def test_baseline_failure_wins_over_upgrade_failure():
    bundle = make_bundle(before=side(build_ok=False), after=side(build_ok=False))
    assert decide(bundle)["decision"] == INSUFFICIENT


def test_uncollected_tests_in_either_side_give_insufficient_evidence():
    assert decide(make_bundle(before=side(tests_ran=False)))["decision"] == INSUFFICIENT
    assert decide(make_bundle(after=side(tests_ran=False)))["decision"] == INSUFFICIENT


def test_new_conflict_rejects():
    diff = empty_diff()
    diff["conflicts"]["introduced"] = ["a 1.0 has requirement b<2, but you have b 2.0"]
    verdict = decide(make_bundle(diff=diff))
    assert verdict["decision"] == REJECT
    assert reason_codes(verdict) == ["new-dependency-conflict"]


def test_new_vulnerability_rejects():
    diff = empty_diff()
    diff["vulnerabilities"]["introduced"] = [{"id": "PYSEC-1", "package": "urllib3"}]
    verdict = decide(make_bundle(diff=diff))
    assert verdict["decision"] == REJECT
    assert reason_codes(verdict) == ["new-vulnerability"]


def test_new_licence_violation_rejects():
    diff = empty_diff()
    diff["licenses"]["introduced"] = [{"package": "chardet", "canonical": "LGPL-2.1"}]
    after = side()
    after["licenses"]["violations"] = [{"package": "chardet", "canonical": "LGPL-2.1"}]
    verdict = decide(make_bundle(diff=diff, after=after))
    assert verdict["decision"] == REJECT
    assert reason_codes(verdict) == ["licence-policy-violation"]


def existing_violation_bundle(strict):
    after = side()
    after["licenses"]["violations"] = [{"package": "certifi", "canonical": "MPL-2.0"}]
    bundle = make_bundle(after=after)
    bundle["options"]["strict_licences"] = strict
    return bundle


def test_old_licence_violation_is_only_a_note_by_default():
    verdict = decide(existing_violation_bundle(strict=False))
    assert verdict["decision"] == ACCEPT
    assert note_codes(verdict) == ["licence-policy-precondition"]


def test_old_licence_violation_blocks_in_strict_mode():
    verdict = decide(existing_violation_bundle(strict=True))
    assert verdict["decision"] == REJECT
    assert reason_codes(verdict) == ["licence-policy-precondition"]


def test_test_regression_rejects_and_lists_tests():
    diff = empty_diff()
    diff["tests"]["regressions"] = [{"test": "tests/test_a.py::test_one"}, {"test": "tests/test_a.py::test_two"}]
    verdict = decide(make_bundle(diff=diff))
    assert verdict["decision"] == REJECT
    assert reason_codes(verdict) == ["test-regression"]
    assert "test_one" in verdict["reasons"][0]["message"]


def test_resolved_vulnerabilities_are_a_note_not_a_reason():
    diff = empty_diff()
    diff["vulnerabilities"]["resolved"] = [{"id": "PYSEC-2", "package": "requests"}]
    verdict = decide(make_bundle(diff=diff))
    assert verdict["decision"] == ACCEPT
    assert note_codes(verdict) == ["vulnerabilities-resolved"]


def test_new_failing_tests_are_a_warning_note():
    diff = empty_diff()
    diff["tests"]["new_failing_tests"] = [{"test": "tests/test_new.py::test_x"}]
    verdict = decide(make_bundle(diff=diff))
    assert verdict["decision"] == ACCEPT
    assert note_codes(verdict) == ["new-failing-tests"]


def test_several_problems_are_all_reported():
    diff = empty_diff()
    diff["conflicts"]["introduced"] = ["x"]
    diff["tests"]["regressions"] = [{"test": "t"}]
    verdict = decide(make_bundle(diff=diff))
    assert reason_codes(verdict) == ["new-dependency-conflict", "test-regression"]


def test_install_conflict_is_reported_as_a_dependency_conflict():
    after = side(build_ok=False, stage="dependency-install")
    after["build"]["failure_output"] = "ERROR: Cannot install a and b because these package versions have conflicting dependencies.\nERROR: ResolutionImpossible"
    verdict = decide(make_bundle(after=after))
    assert verdict["decision"] == REJECT
    assert reason_codes(verdict) == ["upgrade-dependency-conflict"]


def test_plain_install_failure_stays_a_build_failure():
    after = side(build_ok=False, stage="dependency-install")
    after["build"]["failure_output"] = "ERROR: No matching distribution found for pluggy==99.0.0"
    assert reason_codes(decide(make_bundle(after=after))) == ["upgrade-build-failed"]
