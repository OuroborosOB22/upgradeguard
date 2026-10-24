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


import pytest

from upgradeguard.spec import validate_python_name, validate_spec


def spec_with(package="requests", from_version="2.28.2", to_version="2.32.5"):
    return UpgradeSpec(repo_path=".", package=package, from_version=from_version, to_version=to_version)


def test_ordinary_names_and_versions_pass_validation():
    assert validate_spec(spec_with("zope.interface", "6.4.post2", "7.0")) is not None
    assert validate_spec(spec_with("a", "1!2.0+local", "2.0rc1")) is not None


@pytest.mark.parametrize("package", ["", "x y", "x==1", "x\n-r other.txt", "--index-url=http://evil", "x;rm", "-e git+https://x", "a" * 101])
def test_hostile_package_names_are_refused(package):
    with pytest.raises(ValueError):
        validate_spec(spec_with(package=package))


@pytest.mark.parametrize("version", ["", "1.0\n--extra-index-url http://evil", "1.0 ; python_version", "../1.0", "1.0 --hash=sha256:x", "$(id)", "v" * 65])
def test_hostile_versions_are_refused(version):
    with pytest.raises(ValueError):
        validate_spec(spec_with(from_version=version))
    with pytest.raises(ValueError):
        validate_spec(spec_with(to_version=version))


@pytest.mark.parametrize("name", ["python3", "python3.13", "python3.9"])
def test_plain_interpreter_names_are_allowed(name):
    assert validate_python_name(name) == name


@pytest.mark.parametrize("name", ["", "/bin/sh", "python", "python3; ls", "../python3", "python3.13 -c x", "python2.7"])
def test_other_interpreters_are_refused(name):
    with pytest.raises(ValueError):
        validate_python_name(name)


def test_the_runner_refuses_a_hostile_spec_before_doing_anything(tmp_path):
    from upgradeguard.runner import run_upgrade_check
    (tmp_path / "requirements.txt").write_text("requests==1\n")
    bad = UpgradeSpec(repo_path=str(tmp_path), package="requests", from_version="1", to_version="2\n-r evil.txt")
    with pytest.raises(ValueError):
        run_upgrade_check(bad, load_policy(""), evidence_root=str(tmp_path / "e"), work_root=str(tmp_path / "w"))
    assert not (tmp_path / "e").exists()
