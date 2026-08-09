"""Agentic web-search retrieval with complete query and source provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # Static validation remains usable without optional setup.
    OpenAI = None  # type: ignore[assignment,misc]


@dataclass(frozen=True)
class RetrievedSource:
    url: str
    title: str


@dataclass(frozen=True)
class SearchRun:
    reference_claim_id: str
    model: str
    searched_at: str
    output_text: str
    queries: list[str]
    sources: list[RetrievedSource]
    response_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


class AgenticWebSearch:
    """Use hosted agentic web search without domain allowlists or site filters."""

    def __init__(self, *, model: str = "gpt-5.5", reasoning_effort: str = "medium"):
        if OpenAI is None:
            raise RuntimeError("Install the project and configure OPENAI_API_KEY")
        self.client = OpenAI()
        self.model = model
        self.reasoning_effort = reasoning_effort

    def search_reference_claim(self, row: dict[str, str]) -> SearchRun:
        prompt = (
            "Independently research this German cultural benchmark item. Use open web search; "
            "do not restrict yourself to a predefined website list. Prefer current primary, official, "
            "peer-reviewed, corpus, or representative-survey evidence when available, but retain "
            "relevant contrary evidence and regional variation. Separate binding law from policy, "
            "social norms, linguistic usage, values, and individual preference. Return a concise "
            "evidence brief with inline citations. Do not score any model response.\n\n"
            f"Reference claim ID: {row['reference_claim_id']}\n"
            f"Benchmark prompt: {row['prompt_text']}\n"
            f"Verification boundary: {row['reference_claim_text']}\n"
            f"Evidence requirement: {row['evidence_requirement']}\n"
            f"Search brief: {row['search_brief']}"
        )
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": self.reasoning_effort},
            tools=[{"type": "web_search", "search_context_size": "high"}],
            tool_choice="required",
            include=["web_search_call.action.sources"],
            input=prompt,
        )

        queries: list[str] = []
        sources_by_url: dict[str, RetrievedSource] = {}
        for item in response.output:
            if _get(item, "type") == "web_search_call":
                action = _get(item, "action", {})
                action_queries = _get(action, "queries") or []
                if isinstance(action_queries, str):
                    action_queries = [action_queries]
                queries.extend(str(query) for query in action_queries)
                for source in _get(action, "sources", []) or []:
                    url = str(_get(source, "url", "")).strip()
                    if url:
                        sources_by_url[url] = RetrievedSource(
                            url=url,
                            title=str(_get(source, "title", "")).strip(),
                        )

            if _get(item, "type") == "message":
                for content in _get(item, "content", []) or []:
                    for annotation in _get(content, "annotations", []) or []:
                        url = str(_get(annotation, "url", "")).strip()
                        if url:
                            sources_by_url[url] = RetrievedSource(
                                url=url,
                                title=str(_get(annotation, "title", "")).strip(),
                            )

        return SearchRun(
            reference_claim_id=row["reference_claim_id"],
            model=self.model,
            searched_at=datetime.now(UTC).isoformat(),
            output_text=response.output_text,
            queries=queries,
            sources=list(sources_by_url.values()),
            response_id=response.id,
        )
