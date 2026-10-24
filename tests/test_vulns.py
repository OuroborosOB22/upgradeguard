import json

from upgradeguard.checks import vulns
from upgradeguard.checks.vulns import diff_vulnerabilities, normalise_pip_audit, safe_parse, version_key


def finding(package, identifier):
    return {"package": package, "version": "1", "id": identifier}


def test_version_key_orders_numerically():
    assert version_key("2.10.0") > version_key("2.9.9")
    assert version_key("1.26.18") < version_key("2.0.0")
    assert version_key("") == (0,)


def test_safe_parse_skips_noise_before_the_json():
    assert safe_parse('warning text\n{"dependencies": []}') == {"dependencies": []}
    assert safe_parse("no json here") is None
    assert safe_parse("{broken") is None


def test_pip_audit_payload_is_normalised_and_deduplicated():
    payload = {"dependencies": [
        {"name": "Urllib3", "version": "2.0.5", "vulns": [
            {"id": "GHSA-1", "aliases": ["CVE-1"], "fix_versions": ["2.0.7"], "description": "first line\nsecond"},
            {"id": "GHSA-1", "aliases": [], "fix_versions": [], "description": ""},
        ]},
        {"name": "pip", "version": "1", "vulns": [{"id": "SKIP-ME"}]},
        {"name": "clean", "version": "1", "vulns": []},
    ]}
    findings = normalise_pip_audit(payload)
    assert len(findings) == 1
    assert findings[0]["package"] == "urllib3"
    assert findings[0]["summary"] == "first line"


def test_diff_finds_introduced_resolved_and_remaining():
    before = {"findings": [finding("a", "X"), finding("b", "Y")]}
    after = {"findings": [finding("b", "Y"), finding("c", "Z")]}
    diff = diff_vulnerabilities(before, after)
    assert [item["id"] for item in diff["introduced"]] == ["Z"]
    assert [item["id"] for item in diff["resolved"]] == ["X"]
    assert [item["id"] for item in diff["remaining"]] == ["Y"]


def test_offline_scan_uses_the_bundled_advisories(tmp_path, monkeypatch):
    site = tmp_path / "env" / "lib" / "python3.12" / "site-packages"
    dist = site / "urllib3-2.0.5.dist-info"
    dist.mkdir(parents=True)
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: urllib3\nVersion: 2.0.5\n")
    advisories = tmp_path / "advisories.json"
    advisories.write_text(json.dumps({"advisories": [
        {"package": "urllib3", "id": "GHSA-v845", "fixed_in": "2.0.6", "summary": "cookie leak"},
        {"package": "urllib3", "id": "OLD", "fixed_in": "1.0"},
    ]}))
    monkeypatch.setattr(vulns, "FALLBACK_FILE", str(advisories))
    findings = vulns.fallback_scan(str(site))
    assert [item["id"] for item in findings] == ["GHSA-v845"]


def test_audit_falls_back_when_network_is_not_allowed(tmp_path):
    result = vulns.audit_environment("", str(tmp_path), allow_network=False)
    assert result["source"] == "bundled-advisories"
    assert result["available"] is False
