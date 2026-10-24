import json

from upgradeguard.spec import canonical_name, declared_names, load_policy, pin_package, new_run_id, UpgradeSpec


def test_canonical_name_folds_case_and_separators():
    assert canonical_name("Typing_Extensions") == "typing-extensions"
    assert canonical_name("zope.interface") == "zope-interface"
    assert canonical_name("A--B") == "a-b"


def test_pin_replaces_an_existing_line():
    lines, found = pin_package(["requests==2.28.2", "jinja2==3.0.3"], "requests", "2.32.5")
    assert lines == ["requests==2.32.5", "jinja2==3.0.3"]
    assert found is True


def test_pin_matches_regardless_of_case_and_keeps_extras():
    lines, found = pin_package(["Requests[socks]>=2.0"], "requests", "2.32.5")
    assert lines == ["Requests[socks]==2.32.5"]
    assert found is True


def test_pin_appends_when_the_package_is_not_declared():
    lines, found = pin_package(["flask==3.0.0"], "urllib3", "2.0.7")
    assert lines == ["flask==3.0.0", "urllib3==2.0.7"]
    assert found is False


def test_pin_leaves_comments_blanks_and_options_alone():
    original = ["# pinned", "", "-r base.txt", "requests==1.0"]
    lines, _ = pin_package(original, "requests", "2.0")
    assert lines[:3] == original[:3]


def test_pin_does_not_touch_packages_with_a_similar_name():
    lines, found = pin_package(["requests-oauthlib==1.3.1"], "requests", "2.0")
    assert lines[0] == "requests-oauthlib==1.3.1"
    assert found is False


def test_declared_names_skips_comments_and_options():
    names = declared_names(["# note", "", "-e .", "Flask==3.0", "typing_extensions>=4"])
    assert names == ["flask", "typing-extensions"]


def test_run_id_contains_package_and_versions():
    spec = UpgradeSpec(repo_path=".", package="Requests", from_version="2.28.2", to_version="2.32.5")
    run_id = new_run_id(spec)
    assert run_id.endswith("-requests-2_28_2-to-2_32_5")


def test_default_policy_denies_copyleft_and_allows_permissive():
    policy = load_policy("")
    assert "MIT" in policy.allowed
    assert "GPL-3.0" in policy.denied


def test_policy_file_is_loaded_and_upper_cased(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"name": "mine", "allowed": ["mit"], "denied": ["gpl-3.0"],
                                "package_exceptions": {"Some_Pkg": "MIT"}}))
    policy = load_policy(str(path))
    assert policy.name == "mine"
    assert policy.allowed == ["MIT"]
    assert policy.denied == ["GPL-3.0"]
    assert policy.package_exceptions == {"some-pkg": "MIT"}
