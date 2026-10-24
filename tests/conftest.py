import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: runs the real tool against example projects and needs network access")
