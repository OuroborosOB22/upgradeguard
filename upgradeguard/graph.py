import re

from .spec import canonical_name

REQUIRE_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
TOOLING_PACKAGES = {"pip", "setuptools", "wheel", "pkg-resources"}


def split_requirement(raw):
    marker = ""
    body = raw
    if ";" in raw:
        body, marker = raw.split(";", 1)
    match = REQUIRE_NAME.match(body)
    if not match:
        return "", body.strip(), marker.strip()
    name = canonical_name(match.group(1))
    specifier = body[match.end():].strip()
    return name, specifier, marker.strip()


def build_graph(packages, direct_names, include_tooling=False):
    by_name = {}
    for package in packages:
        if not include_tooling and package.canonical in TOOLING_PACKAGES:
            continue
        by_name[package.canonical] = package

    nodes = {}
    for name, package in by_name.items():
        nodes[name] = {
            "name": package.name,
            "canonical": name,
            "version": package.version,
            "license_raw": package.license_raw,
            "license_source": package.license_source,
            "direct": name in direct_names,
            "depth": 0 if name in direct_names else -1,
            "requires": [],
            "required_by": [],
        }

    edges = []
    for name, package in by_name.items():
        for raw in package.requires:
            child, specifier, marker = split_requirement(raw)
            if not child or child not in nodes:
                continue
            edges.append({
                "parent": name,
                "child": child,
                "specifier": specifier,
                "marker": marker,
                "raw": raw,
            })
            if child not in nodes[name]["requires"]:
                nodes[name]["requires"].append(child)
            if name not in nodes[child]["required_by"]:
                nodes[child]["required_by"].append(name)

    assign_depth(nodes, direct_names)
    return {
        "nodes": nodes,
        "edges": edges,
        "direct": sorted(name for name in nodes if nodes[name]["direct"]),
        "transitive": sorted(name for name in nodes if not nodes[name]["direct"]),
        "total": len(nodes),
    }


def assign_depth(nodes, direct_names):
    frontier = [name for name in nodes if name in direct_names]
    for name in frontier:
        nodes[name]["depth"] = 0
    level = 0
    seen = set(frontier)
    while frontier:
        level += 1
        following = []
        for name in frontier:
            for child in nodes[name]["requires"]:
                if child in seen:
                    continue
                seen.add(child)
                nodes[child]["depth"] = level
                following.append(child)
        frontier = following
    for name in nodes:
        if nodes[name]["depth"] < 0:
            nodes[name]["depth"] = 99


def diff_graphs(before, after):
    before_nodes = before["nodes"]
    after_nodes = after["nodes"]
    added = []
    removed = []
    changed = []
    unchanged = []

    for name in sorted(after_nodes):
        if name not in before_nodes:
            added.append({
                "name": name,
                "version": after_nodes[name]["version"],
                "direct": after_nodes[name]["direct"],
                "license_raw": after_nodes[name]["license_raw"],
            })
    for name in sorted(before_nodes):
        if name not in after_nodes:
            removed.append({
                "name": name,
                "version": before_nodes[name]["version"],
                "direct": before_nodes[name]["direct"],
            })
    for name in sorted(before_nodes):
        if name not in after_nodes:
            continue
        old = before_nodes[name]["version"]
        new = after_nodes[name]["version"]
        if old != new:
            changed.append({
                "name": name,
                "from_version": old,
                "to_version": new,
                "direct": after_nodes[name]["direct"],
            })
        else:
            unchanged.append(name)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged_count": len(unchanged),
        "before_total": len(before_nodes),
        "after_total": len(after_nodes),
    }
