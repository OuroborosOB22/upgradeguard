import pytest

from feedreader.client import load_feed, newest, titles


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status >= 400:
            raise ValueError("status %s" % self.status)


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return self.response


FEED = {"items": [
    {"title": "old", "published": "2024-01-01"},
    {"title": "new", "published": "2024-06-01"},
]}


def test_load_feed_returns_payload():
    client = FakeClient(FakeResponse(FEED))
    assert load_feed("http://example.test/feed", client=client) == FEED


def test_load_feed_uses_timeout():
    client = FakeClient(FakeResponse(FEED))
    load_feed("http://example.test/feed", client=client)
    assert client.calls[0][1] == 4


def test_load_feed_raises_on_error():
    client = FakeClient(FakeResponse({}, status=404))
    with pytest.raises(ValueError):
        load_feed("http://example.test/feed", client=client)


def test_titles_lists_every_item():
    assert titles(FEED) == ["old", "new"]


def test_newest_picks_latest_published():
    assert newest(FEED)["title"] == "new"


def test_newest_handles_empty_feed():
    assert newest({"items": []}) is None
