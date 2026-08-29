import requests

DEFAULT_TIMEOUT = 4


def load_feed(url, client=None, timeout=DEFAULT_TIMEOUT):
    caller = client or requests
    response = caller.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def titles(feed):
    return [item.get("title", "untitled") for item in feed.get("items", [])]


def newest(feed):
    items = feed.get("items", [])
    if not items:
        return None
    return sorted(items, key=lambda item: item.get("published", ""))[-1]
