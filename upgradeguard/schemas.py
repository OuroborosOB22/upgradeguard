import json
import os

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CONTRACT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "contracts", "v1")
SCHEMA_NAMES = ["request", "evidence", "prediction_request", "prediction_response", "snapshot", "comparison", "worker_result", "explanation_graph"]


def load_schema(name):
    with open(os.path.join(CONTRACT_DIR, name + ".schema.json")) as handle:
        return json.load(handle)


def build_registry():
    registry = Registry()
    for name in SCHEMA_NAMES:
        contents = load_schema(name)
        registry = registry.with_resource(contents["$id"], Resource.from_contents(contents))
    return registry


def problems(name, payload):
    validator = Draft202012Validator(load_schema(name), registry=build_registry())
    return ["%s: %s" % ("/".join(str(part) for part in error.path) or "(top)", error.message[:200]) for error in validator.iter_errors(payload)]


class ContractError(ValueError):
    pass


def require_valid(name, payload):
    found = problems(name, payload)
    if found:
        raise ContractError("%s is not valid contract v1: %s" % (name, "; ".join(found[:5])))
    return payload
