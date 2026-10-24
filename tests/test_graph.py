from upgradeguard.graph import build_graph, diff_graphs, split_requirement
from upgradeguard.metadata import InstalledPackage


def package(name, version, requires=None):
    return InstalledPackage(name=name, canonical=name.lower().replace("_", "-"), version=version, requires=requires or [])


def test_split_requirement_reads_name_specifier_and_marker():
    assert split_requirement("urllib3<3,>=1.21.1") == ("urllib3", "<3,>=1.21.1", "")
    assert split_requirement('colorama; platform_system == "Windows"') == ("colorama", "", 'platform_system == "Windows"')
    assert split_requirement("Typing_Extensions>=4")[0] == "typing-extensions"


def test_graph_marks_direct_and_transitive_packages():
    packages = [package("requests", "2.0", ["urllib3>=1"]), package("urllib3", "1.5"), package("pip", "24.0")]
    graph = build_graph(packages, {"requests"})
    assert graph["direct"] == ["requests"]
    assert graph["transitive"] == ["urllib3"]
    assert graph["nodes"]["urllib3"]["depth"] == 1
    assert graph["nodes"]["urllib3"]["required_by"] == ["requests"]
    assert "pip" not in graph["nodes"]


def test_requirements_missing_from_the_environment_are_ignored():
    graph = build_graph([package("a", "1", ["ghost>=1"])], {"a"})
    assert graph["edges"] == []


def test_diff_reports_added_removed_and_changed():
    before = build_graph([package("a", "1"), package("b", "1"), package("c", "1")], {"a"})
    after = build_graph([package("a", "2"), package("c", "1"), package("d", "1")], {"a"})
    diff = diff_graphs(before, after)
    assert [item["name"] for item in diff["added"]] == ["d"]
    assert [item["name"] for item in diff["removed"]] == ["b"]
    assert diff["changed"] == [{"name": "a", "from_version": "1", "to_version": "2", "direct": True}]
    assert diff["unchanged_count"] == 1
