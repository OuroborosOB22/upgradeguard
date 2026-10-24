from upgradeguard import health
from upgradeguard.history import History
from upgradeguard.spec import load_policy

EXAMPLE = "flask==3.0.0\nnumpy>=1.24\nnumpy==1.26.4\npandas>=2.0\nrequests\n"


def fake_lookup(name):
    table = {"flask": ("3.1.0", "BSD-3-Clause"), "numpy": ("2.1.0", "BSD License"), "pandas": ("2.2.0", "BSD-3-Clause"), "requests": ("2.32.0", "Apache-2.0"),
             "gpl-thing": ("1.0", "GNU General Public License v3 (GPLv3)")}
    if name == "ghost":
        return {"status": "not_found"}
    if name == "offline":
        return {"status": "unavailable", "reason": "URLError"}
    if name == "mystery":
        return {"status": "found", "latest": "1", "summary": "", "licence": "", "requires_python": ""}
    version, licence = table[name]
    return {"status": "found", "latest": version, "summary": "x", "licence": licence, "requires_python": ""}


def run(text):
    return health.analyse(text, load_policy(""), fake_lookup)


def test_the_proposal_example_has_one_duplicate_and_no_conflict():
    report = run(EXAMPLE)
    assert report["total_specifications"] == 5 and report["unique_packages"] == 4
    assert len(report["duplicates"]) == 1 and report["duplicates"][0]["package"] == "numpy"
    assert report["conflicts"] == [] and report["invalid"] == []
    assert report["score"] == 92 and report["status"] == "Good"


def test_incompatible_ranges_are_a_conflict():
    report = run("numpy < 1.25\nnumpy >= 1.26\n")
    assert [item["package"] for item in report["conflicts"]] == ["numpy"]
    assert report["score"] == 100 - 8 - 20


def test_compatible_ranges_are_not_a_conflict():
    assert health.has_conflict([">=1.0", "<2.0"]) is False
    assert health.has_conflict(["==1.5.*", ">=1.5.2"]) is False
    assert health.has_conflict([">=2.0", "<1.0"]) is True


def test_invalid_lines_are_listed_with_the_reason():
    report = run("requests==\n!!! bad\nflask\n")
    assert len(report["invalid"]) == 2 and report["valid_specifications"] == 1
    assert report["score"] == 100 - 15 * 2


def test_options_and_comments_are_skipped_not_counted():
    report = run("# comment\n-r other.txt\n--index-url https://example.org/simple\nflask  # inline\n\n")
    assert report["total_specifications"] == 1 and len(report["skipped_lines"]) == 2


def test_licence_and_metadata_outcomes_are_kept_separate():
    report = run("gpl-thing\nghost\noffline\nmystery\n")
    by_name = {row["package"]: row for row in report["packages"]}
    assert by_name["gpl-thing"]["licence_status"] == "denied"
    assert by_name["ghost"]["metadata"] == "not_found"
    assert by_name["offline"]["metadata"] == "unavailable"
    assert by_name["mystery"]["licence"] == "UNKNOWN" and report["unknown_licences"] == 1
    assert report["metadata_unavailable"] == 1
    assert report["score"] == 100 - 10 - 10


def test_score_never_goes_below_zero():
    assert health.score_for({"conflict": 10})[0] == 0


def test_a_huge_or_oversized_file_is_refused():
    import pytest
    with pytest.raises(health.BadFile):
        health.parse("x" * (health.MAX_BYTES + 1))
    with pytest.raises(health.BadFile):
        health.parse("\n".join("pkg%d" % index for index in range(health.MAX_SPECS + 1)))


def test_history_stores_and_returns_records(tmp_path):
    history = History(str(tmp_path / "db" / "history.db"))
    first = history.add("health", "requirements.txt", "92/100 Good", {"score": 92})
    history.add("upgrade", "requests 1 to 2", "Accept", {"x": 1}, run_id="run-1")
    assert [row["kind"] for row in history.recent()] == ["upgrade", "health"]
    assert history.get(first)["payload"] == {"score": 92}
    assert history.has_run("run-1") and not history.has_run("run-2")
    assert history.get(999) is None


def test_history_survives_hostile_text(tmp_path):
    history = History(str(tmp_path / "h.db"))
    history.add("health", "'); drop table analyses; --", "x", {})
    assert len(history.recent()) == 1
