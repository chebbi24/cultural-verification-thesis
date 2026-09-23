import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import requests
from cultverify import Config, CulturalVerifier
from cultverify.cli import main
from cultverify.llm import HTTPModel, SemanticSession, StageError, strict_schema
from cultverify.retrieval import TavilyRetriever
from cultverify.schemas import InitialQuestions, QueryDraft, RunTrace
from conftest import FixtureLLM, PROMPT, RESPONSE


def test_ollama_stateless_structured_contract():
    config = Config(verifier_model_id="frozen-model:revision")
    client = HTTPModel(config)
    response = Mock()
    response.json.return_value = {"message": {"content": '{"text":"query"}'}}
    with patch("cultverify.llm.requests.post", return_value=response) as post:
        client.complete(
            stage="query_rewriter_v1",
            system="Instructions",
            payload={"question": "first"},
            schema=QueryDraft.model_json_schema(),
        )
        client.complete(
            stage="query_rewriter_v1",
            system="Instructions",
            payload={"question": "second"},
            schema=QueryDraft.model_json_schema(),
        )
    body = post.call_args.kwargs["json"]
    assert body["format"] == QueryDraft.model_json_schema()
    assert body["think"] is False
    assert body["options"]["temperature"] == 0 and body["stream"] is False
    assert len(body["messages"]) == 2 and "first" not in json.dumps(body)
    assert post.call_args.kwargs["timeout"] == config.llm_timeout


def test_openrouter_contract_same_model_no_fallback():
    config = Config(verifier_model_provider="openrouter", verifier_model_id="provider/frozen-revision")
    client = HTTPModel(config, api_key="test-only-placeholder")
    response = Mock()
    response.json.return_value = {"choices": [{"message": {"content": '{"text":"query"}'}}]}
    with patch("cultverify.llm.requests.post", return_value=response) as post:
        raw = client.complete(
            stage="query_rewriter_v1",
            system="Instructions",
            payload={"question": "q"},
            schema=QueryDraft.model_json_schema(),
        )
    body = post.call_args.kwargs["json"]
    assert json.loads(raw)["text"] == "query"
    assert body["model"] == config.verifier_model_id
    assert body["provider"] == {"require_parameters": True, "allow_fallbacks": False}
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "test-only-placeholder" not in json.dumps(body)
    assert "plugins" not in body


def test_provider_tuple_schema_compatible():
    schema = strict_schema(InitialQuestions.model_json_schema())
    assert "prefixItems" not in json.dumps(schema)
    assert schema["properties"]["questions"]["minItems"] == 2
    assert schema["properties"]["questions"]["maxItems"] == 2


def test_tavily_contract_and_provenance():
    client = TavilyRetriever("test-only-placeholder")
    response = Mock()
    response.json.return_value = {
        "results": [{"url": "https://example.org/source", "title": "Title", "content": "Source text", "score": 0.7}]
    }
    with patch("cultverify.retrieval.requests.post", return_value=response) as post:
        docs = client.search("neutral query", top_k=3, timeout=12)
    body = post.call_args.kwargs["json"]
    assert body["include_answer"] is False and body["query"] == "neutral query"
    assert docs[0].rank == 1 and docs[0].provider_score == 0.7
    assert docs[0].query == "neutral query" and docs[0].retrieved_at
    assert post.call_args.kwargs["timeout"] == 12


def test_transport_retry_is_traced(setup):
    config, _, _, _ = setup
    llm = FixtureLLM(config)
    original = llm.complete
    count = 0

    def complete(**kwargs):
        nonlocal count
        count += 1
        if count == 1:
            raise requests.Timeout("test only")
        return original(**kwargs)

    llm.complete = complete
    session = SemanticSession(llm, config)
    result = session.call("query_rewriter_v1", {"question": {"text": "query"}}, QueryDraft)
    assert result.text == "query"
    assert [c.error for c in session.calls] == ["Timeout", None]


def test_bad_credentials_not_retried(setup):
    config, _, _, _ = setup
    response = Mock(status_code=401)
    llm = FixtureLLM(config, overrides={"query_rewriter_v1": requests.HTTPError(response=response)})
    session = SemanticSession(llm, config)
    with pytest.raises(StageError, match=r"HTTPError status=401"):
        session.call("query_rewriter_v1", {}, QueryDraft)
    assert len(session.calls) == 1
    assert session.calls[0].error == "HTTPError:401"


def test_wrong_model_configuration_rejected(setup):
    config, llm, retriever, _ = setup
    other = config.model_copy(update={"verifier_model_id": "another-model"})
    with pytest.raises(ValueError):
        CulturalVerifier(llm=llm, retriever=retriever, config=other)


def test_cli_verify_and_rank(setup, tmp_path, capsys, monkeypatch):
    _, _, retriever, _ = setup
    for key in ("CULTVERIFY_MODEL", "CULTVERIFY_PROVIDER", "CULTVERIFY_MODE", "OLLAMA_URL"):
        monkeypatch.delenv(key, raising=False)
    common = [
        "--model",
        "fixture",
        "--cache-directory",
        str(tmp_path / "cache"),
        "--trace-directory",
        str(tmp_path / "traces"),
    ]
    with (
        patch("cultverify.cli.HTTPModel", side_effect=lambda config, key: FixtureLLM(config)),
        patch("cultverify.cli.TavilyRetriever", return_value=retriever),
    ):
        assert main(["verify", "--prompt", PROMPT, "--response", RESPONSE, *common]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["status"] == "completed" and result["overall_score"] == 1
        responses = tmp_path / "responses.json"
        responses.write_text(json.dumps([RESPONSE] * 4))
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text(PROMPT)
        assert main(["rank", "--prompt-file", str(prompt_file), "--responses-file", str(responses), *common]) == 0
        assert json.loads(capsys.readouterr().out)["winner"] == "no_clear_winner"


def test_cli_requires_model(monkeypatch, capsys):
    monkeypatch.delenv("CULTVERIFY_MODEL", raising=False)
    assert main(["verify", "--prompt", PROMPT, "--response", RESPONSE]) == 2
    assert "verifier_model_id" in capsys.readouterr().err


def test_model_prompt_does_not_execute_document_instructions(setup):
    _, llm, _, verifier = setup
    verifier.verify(PROMPT, RESPONSE)
    for call in llm.calls:
        assert "untrusted task data" in call["system"]


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("CULTVERIFY_RUN_LIVE") != "1", reason="Requires explicit live-test opt-in, model and Tavily credentials"
)
def test_real_live_then_replay(tmp_path):
    config = Config(
        verifier_model_provider=os.getenv("CULTVERIFY_PROVIDER", "ollama"),
        verifier_model_id=os.environ["CULTVERIFY_MODEL"],
        cache_directory=tmp_path / "evidence",
        trace_directory=tmp_path / "traces",
    )
    llm = HTTPModel(config, os.getenv("OPENROUTER_API_KEY"))
    retriever = TavilyRetriever(os.environ["TAVILY_API_KEY"])
    prompt = "Explain the formal opening hours and visiting arrangements for the British Museum in London."
    response = "Check the British Museum’s official visitor information for current opening hours and arrangements."
    live = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(prompt, response)
    assert live.status == "completed" and live.evidence
    replay_config = config.model_copy(update={"mode": "REPLAY"})
    replay = CulturalVerifier(
        llm=HTTPModel(replay_config, os.getenv("OPENROUTER_API_KEY")), retriever=None, config=replay_config
    ).verify(prompt, response)
    assert replay.status == "completed"
    assert [s for b in live.evidence for s in b.snapshots] == [s for b in replay.evidence for s in b.snapshots]
    assert RunTrace.model_validate_json(Path(replay.trace_path).read_text()).mode == "REPLAY"


def test_malformed_provider_response_is_traced(setup):
    config, _, _, _ = setup
    config = config.model_copy(update={"verifier_model_provider": "ollama"})
    session = SemanticSession(HTTPModel(config), config)
    response = Mock()
    response.json.return_value = {"error": "unexpected shape"}
    with patch("cultverify.llm.requests.post", return_value=response):
        with pytest.raises(StageError):
            session.call("query_rewriter_v1", {"question": {"text": "x"}}, QueryDraft)
    assert session.calls[0].error == "ProviderResponseError"
