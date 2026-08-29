import pytest

from notesapp.fetch import fetch_note, summarise


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


def test_fetch_note_returns_payload():
    client = FakeClient(FakeResponse({"title": "a", "body": "b c"}))
    assert fetch_note("http://example.test/1", client=client) == {"title": "a", "body": "b c"}


def test_fetch_note_passes_a_timeout():
    client = FakeClient(FakeResponse({}))
    fetch_note("http://example.test/1", client=client)
    assert client.calls[0][1] == 5


def test_fetch_note_raises_on_error_status():
    client = FakeClient(FakeResponse({}, status=500))
    with pytest.raises(ValueError):
        fetch_note("http://example.test/1", client=client)


def test_summarise_counts_words():
    assert summarise({"title": "t", "body": "one two three"})["word_count"] == 3


def test_summarise_flags_empty_body():
    assert summarise({"title": "t", "body": "   "})["empty"] is True
