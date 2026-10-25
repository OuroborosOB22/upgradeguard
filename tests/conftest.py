import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def pytest_addoption(parser):
    parser.addoption("--slow", action="store_true", default=False, help="also run the slow tests that build real environments")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: builds real environments and needs network access")
    config.addinivalue_line("markers", "container: also needs a running Docker daemon")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--slow"):
        return
    chosen = [item for item in items if "slow" not in item.keywords]
    config.hook.pytest_deselected(items=[item for item in items if "slow" in item.keywords])
    items[:] = chosen
