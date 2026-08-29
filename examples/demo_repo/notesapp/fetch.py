import requests

DEFAULT_TIMEOUT = 5


def fetch_note(url, client=None, timeout=DEFAULT_TIMEOUT):
    caller = client or requests
    response = caller.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def summarise(payload):
    body = payload.get("body", "")
    return {
        "title": payload.get("title", "untitled"),
        "word_count": len(body.split()),
        "empty": body.strip() == "",
    }
