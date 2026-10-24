import os
import re

from ..util import write_json

LICENSE_PATTERNS = [
    ("AGPL-3.0", ["AGPL-3", "AFFERO GENERAL PUBLIC LICENSE V3", "AGPLV3", "AGPL"]),
    ("LGPL-3.0", ["LGPL-3", "LESSER GENERAL PUBLIC LICENSE V3", "LGPLV3"]),
    ("LGPL-2.1", ["LGPL-2", "LESSER GENERAL PUBLIC LICENSE V2", "LGPLV2", "LGPL"]),
    ("GPL-3.0", ["GPL-3", "GENERAL PUBLIC LICENSE V3", "GPLV3"]),
    ("GPL-2.0", ["GPL-2", "GENERAL PUBLIC LICENSE V2", "GPLV2"]),
    ("SSPL-1.0", ["SSPL"]),
    ("MPL-2.0", ["MPL-2", "MOZILLA PUBLIC LICENSE 2"]),
    ("APACHE-2.0", ["APACHE-2", "APACHE 2", "APACHE SOFTWARE LICENSE", "APACHE LICENSE"]),
    ("BSD-3-CLAUSE", ["BSD-3", "BSD 3", "NEW BSD", "MODIFIED BSD"]),
    ("BSD-2-CLAUSE", ["BSD-2", "BSD 2", "SIMPLIFIED BSD"]),
    ("MIT", ["MIT", "EXPAT"]),
    ("ISC", ["ISC"]),
    ("PSF-2.0", ["PYTHON SOFTWARE FOUNDATION", "PSF"]),
    ("PYTHON-2.0", ["PYTHON LICENSE", "PYTHON-2"]),
    ("UNLICENSE", ["UNLICENSE", "PUBLIC DOMAIN"]),
    ("ZLIB", ["ZLIB"]),
    ("BSD", ["BSD"]),
]

UNKNOWN = "UNKNOWN"


def normalise_license(raw):
    if not raw:
        return UNKNOWN
    text = raw.upper()
    if text.startswith("LICENSE ::"):
        text = text.split("::")[-1].strip()
    text = re.sub(r"\s+", " ", text).strip()
    for canonical, needles in LICENSE_PATTERNS:
        for needle in needles:
            if needle in text:
                return canonical
    return UNKNOWN


def split_expression(raw):
    if not raw:
        return []
    parts = re.split(r"\s+OR\s+|\s+AND\s+", raw, flags=re.IGNORECASE)
    return [part.strip(" ()") for part in parts if part.strip(" ()")]


TOKENS = re.compile(r"(\(|\)|\s+AND\s+|\s+OR\s+)", re.IGNORECASE)


def tokenize(raw):
    pieces = [piece.strip() for piece in TOKENS.split(raw)]
    return [piece.upper() if piece.upper() in ("AND", "OR") else piece for piece in pieces if piece]


def parse_expression(tokens):
    def either(position):
        node, position = both(position)
        parts = [node]
        while position < len(tokens) and tokens[position] == "OR":
            node, position = both(position + 1)
            parts.append(node)
        return (("OR", parts) if len(parts) > 1 else parts[0]), position

    def both(position):
        node, position = single(position)
        parts = [node]
        while position < len(tokens) and tokens[position] == "AND":
            node, position = single(position + 1)
            parts.append(node)
        return (("AND", parts) if len(parts) > 1 else parts[0]), position

    def single(position):
        if position >= len(tokens) or tokens[position] in ("AND", "OR", ")"):
            raise ValueError("unexpected token")
        if tokens[position] == "(":
            node, position = either(position + 1)
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("missing parenthesis")
            return node, position + 1
        return tokens[position], position + 1

    tree, position = either(0)
    if position != len(tokens):
        raise ValueError("trailing tokens")
    return tree


OPERATOR_WORD = re.compile(r"(^|\s)(AND|OR)(\s|$)", re.IGNORECASE)
OPERATOR_BETWEEN = re.compile(r"\s(AND|OR)\s", re.IGNORECASE)


def judge_leaf(raw, policy, inside_expression=False):
    if inside_expression and OPERATOR_WORD.search(raw):
        raise ValueError("misplaced operator")
    canonical = normalise_license(raw)
    if canonical in policy.allowed:
        return {"status": "allowed", "canonical": canonical, "rule": "in allowed list"}
    if canonical in policy.denied:
        return {"status": "denied", "canonical": canonical, "rule": "in denied list"}
    if canonical == UNKNOWN:
        return {"status": "denied" if policy.unknown_action == "fail" else "unknown", "canonical": UNKNOWN, "rule": "licence could not be identified"}
    return {"status": "unknown", "canonical": canonical, "rule": "not listed in policy"}


def judge_tree(node, policy):
    if isinstance(node, str):
        return judge_leaf(node, policy, inside_expression=True)
    kind, parts = node
    outcomes = [judge_tree(part, policy) for part in parts]
    statuses = [item["status"] for item in outcomes]
    canonical = (" AND " if kind == "AND" else " OR ").join(dict.fromkeys(item["canonical"] for item in outcomes))
    if kind == "AND":
        status = "denied" if "denied" in statuses else ("allowed" if set(statuses) == {"allowed"} else "unknown")
        rule = "every part of an AND expression must be allowed"
    else:
        status = "allowed" if "allowed" in statuses else ("denied" if "denied" in statuses else "unknown")
        rule = "one allowed choice in an OR expression is enough"
    return {"status": status, "canonical": canonical, "rule": rule}


def evaluate_package(package_name, raw, policy):
    exception = policy.package_exceptions.get(package_name)
    if exception:
        return {"status": "allowed", "canonical": exception.upper(), "rule": "package exception"}
    if not raw or not OPERATOR_BETWEEN.search(raw):
        return judge_leaf(raw or "", policy)
    try:
        return judge_tree(parse_expression(tokenize(raw)), policy)
    except ValueError:
        parts = [piece for piece in tokenize(raw) if piece not in ("AND", "OR", "(", ")")]
        denied = any(judge_leaf(part, policy)["status"] == "denied" for part in parts)
        return {"status": "denied" if denied else "unknown", "canonical": UNKNOWN, "rule": "the licence expression could not be read, so it is never treated as allowed"}


def check_licenses(graph, policy, output_dir):
    entries = []
    for name in sorted(graph["nodes"]):
        node = graph["nodes"][name]
        outcome = evaluate_package(name, node["license_raw"], policy)
        entries.append({
            "package": name,
            "version": node["version"],
            "direct": node["direct"],
            "license_raw": node["license_raw"],
            "license_source": node["license_source"],
            "canonical": outcome["canonical"],
            "status": outcome["status"],
            "rule": outcome["rule"],
        })

    report = {
        "policy": policy.name,
        "entries": entries,
        "violations": [item for item in entries if item["status"] == "denied"],
        "unknown": [item for item in entries if item["status"] == "unknown"],
        "allowed_count": len([item for item in entries if item["status"] == "allowed"]),
    }
    write_json(os.path.join(output_dir, "licenses.json"), report)
    return report


def diff_licenses(before, after):
    before_bad = {item["package"] for item in before.get("violations", [])}
    after_index = {item["package"]: item for item in after.get("violations", [])}
    before_index = {item["package"]: item for item in before.get("violations", [])}

    before_unknown = {item["package"] for item in before.get("unknown", [])}
    after_unknown_index = {item["package"]: item for item in after.get("unknown", [])}

    return {
        "introduced": [after_index[name] for name in sorted(set(after_index) - before_bad)],
        "resolved": [before_index[name] for name in sorted(before_bad - set(after_index))],
        "remaining": [after_index[name] for name in sorted(set(after_index) & before_bad)],
        "new_unknown": [after_unknown_index[name] for name in sorted(set(after_unknown_index) - before_unknown)],
    }
