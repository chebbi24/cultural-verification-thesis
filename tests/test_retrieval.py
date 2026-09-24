import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from cultverify import Config, CulturalVerifier
from cultverify.retrieval import RetrievalError, SnapshotStore, exclusion_reason, filter_documents
from cultverify.schemas import SearchQuery
from conftest import FixtureLLM, FixtureRetriever, PROMPT, RESPONSE, document


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/chebbi24/cultural-verification-thesis/blob/main/key.csv",
        "https://raw.githubusercontent.com/chebbi24/cultural-verification-thesis/main/key.csv",
        "https://api.github.com/repos/chebbi24/cultural-verification-thesis/contents/key",
        "file:///data/annotations.csv",
        "/local/labels.csv",
        "https://example.org/results/winners",
        "https://example.org/annotations/labels.csv",
        "https://example.org/human_labels.csv",
        "https://example.org/silver_labels.csv",
    ],
)
def test_leakage_filter(setup, url):
    config, _, _, _ = setup
    assert exclusion_reason(url, config)


def test_configured_benchmark_exclusions(setup):
    config, _, _, _ = setup
    config = config.model_copy(
        update={
            "excluded_domains": ("answers.example",),
            "excluded_repos": ("owner/benchmark",),
            "excluded_paths": ("*/answer-key/*",),
        }
    )
    for url in [
        "https://sub.answers.example/x",
        "https://github.com/owner/benchmark/blob/main/x",
        "https://site.example/answer-key/x",
    ]:
        assert exclusion_reason(url, config)
    assert not exclusion_reason("https://answers.example.evil.org/x", config)
    assert not exclusion_reason("https://github.com/owner/benchmark-not-the-same/blob/main/x", config)


def test_filter_logs_and_deduplicates(setup):
    config, _, _, _ = setup
    docs = (
        document(),
        document(url="https://example.org/event#part"),
        document(url="https://another.example/copy"),
        document(url="https://github.com/chebbi24/cultural-verification-thesis/blob/main/key.csv"),
    )
    accepted, filtered = filter_documents(docs, config)
    assert len(accepted) == 1 and len(filtered) == 3
    assert any(f.reason == "excluded repository" for f in filtered)


def test_missing_replay_snapshot_does_not_fallback(setup):
    config, _, _, _ = setup
    config = config.model_copy(update={"mode": "REPLAY"})
    store = SnapshotStore(config, None)
    with pytest.raises(RetrievalError):
        store.get(SearchQuery(query_id="q", question_id="question", text="missing", round=1))
    result = CulturalVerifier(llm=FixtureLLM(config), retriever=None, config=config).verify(PROMPT, RESPONSE)
    assert result.status == "failed" and "Missing frozen" in result.errors[0]
    assert Path(result.trace_path).exists()


def test_snapshot_content_corruption_detected(setup):
    config, _, _, verifier = setup
    result = verifier.verify(PROMPT, RESPONSE)
    snap = result.evidence[0].snapshots[0]
    path = config.cache_directory / f"{snap.snapshot_id}.json"
    raw = json.loads(path.read_text())
    raw["documents"][0]["text"] = "tampered"
    path.write_text(json.dumps(raw))
    with pytest.raises(RetrievalError):
        SnapshotStore(config.model_copy(update={"mode": "REPLAY"}), None).read_by_id(snap.snapshot_id)


def test_malformed_replay_snapshot_is_reported_cleanly(setup):
    config, _, _, _ = setup
    config = config.model_copy(update={"mode": "REPLAY"})
    store = SnapshotStore(config, None)
    snapshot_id = "snapshot_" + "a" * 24
    path = config.cache_directory / f"{snapshot_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(RetrievalError, match="Malformed frozen snapshot"):
        store.read_by_id(snapshot_id)


def test_round_and_config_limits():
    with pytest.raises(ValidationError):
        SearchQuery(query_id="q", question_id="q", text="x", round=3)
    with pytest.raises(ValidationError):
        Config(verifier_model_id="test", max_retrieval_rounds=3)
    with pytest.raises(ValidationError):
        Config(verifier_model_id="test", max_material_targets=4)


def test_followup_replay_keeps_schedule(setup):
    config, _, _, _ = setup
    retriever = FixtureRetriever(empty=True)
    live = CulturalVerifier(llm=FixtureLLM(config), retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    config = config.model_copy(update={"mode": "REPLAY"})
    llm = FixtureLLM(config, overrides={"followup_v1": AssertionError("Must reuse followup schedule")})
    replay = CulturalVerifier(llm=llm, retriever=None, config=config).verify(PROMPT, RESPONSE)
    assert live.status == replay.status == "completed"
    assert live.evidence[0].queries == replay.evidence[0].queries
    assert replay.evidence[0].memos[-1].sufficiency == "insufficient"


def test_existing_live_schedule_reuses_frozen_queries(setup):
    config, _, retriever, verifier = setup
    live = verifier.verify(PROMPT, RESPONSE)
    llm = FixtureLLM(config, overrides={"query_rewriter_v1": AssertionError("Use existing schedule")})
    repeated = CulturalVerifier(llm=llm, retriever=retriever, config=config).verify(PROMPT, RESPONSE)
    assert repeated.status == "completed" and live.evidence[0].snapshots == repeated.evidence[0].snapshots


def test_corrupt_schedule_returns_traced_failure(setup):
    config, _, _, verifier = setup
    verifier.verify(PROMPT, RESPONSE)
    path = next(config.cache_directory.glob("schedule_*.json"))
    path.write_text("{}")
    config = config.model_copy(update={"mode": "REPLAY"})
    replay = CulturalVerifier(llm=FixtureLLM(config), retriever=None, config=config).verify(PROMPT, RESPONSE)
    assert replay.status == "failed" and Path(replay.trace_path).exists()
