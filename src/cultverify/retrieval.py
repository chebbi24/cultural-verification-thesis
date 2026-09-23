"""Provider-neutral search, provenance exclusions, and immutable evidence snapshots."""

import fnmatch
import json
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlsplit, urlunsplit
import requests
from pydantic import ValidationError
from .config import PIPELINE_VERSION, Config
from .schemas import FilteredResult, RetrievedDocument, RetrievalSnapshot, SearchQuery
from .trace import digest, stable_id, timestamp, write_json


class RetrievalError(RuntimeError):
    pass


class Retriever(Protocol):
    provider: str

    def search(self, query: str, *, top_k: int, timeout: float) -> tuple[RetrievedDocument, ...]: ...


class TavilyRetriever:
    provider = "tavily"

    def __init__(self, api_key: str, search_depth="advanced"):
        if not api_key:
            raise ValueError("TAVILY_API_KEY is required in LIVE mode")
        self._api_key = api_key
        self.search_depth = search_depth

    def search(self, query, *, top_k, timeout):
        response = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "query": query,
                "topic": "general",
                "search_depth": self.search_depth,
                "max_results": top_k,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        try:
            data = response.json()
            results = data["results"]
            if not isinstance(results, list):
                raise TypeError("results must be a list")
        except (ValueError, KeyError, TypeError) as exc:
            raise RetrievalError("Malformed search provider response") from exc

        documents = []
        for rank, item in enumerate(results, 1):
            if not isinstance(item, dict):
                raise RetrievalError("Malformed search result item")
            url = item.get("url")
            title = item.get("title") or ""
            content = item.get("content") or ""
            if not isinstance(url, str) or not isinstance(title, str) or not isinstance(content, str):
                raise RetrievalError("Malformed search result fields")
            if not url.strip() or not content.strip():
                continue
            documents.append(
                RetrievedDocument(
                    document_id=stable_id("doc", [canonical_url(url), content]),
                    query=query,
                    url=url,
                    title=title,
                    text=content,
                    rank=rank,
                    provider_score=item.get("score"),
                    retrieved_at=timestamp(),
                    content_hash=digest(content),
                )
            )
        return tuple(documents)


def canonical_url(url):
    parts = urlsplit(url)
    # Preserve query strings: distinct query-based pages can contain different evidence.
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), unquote(parts.path).rstrip("/"), parts.query, ""))


def exclusion_reason(url, config):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = unquote(parts.path).lower()
    if parts.scheme not in ("http", "https") or not host:
        return "non-web/local resource"
    for domain in config.excluded_domains:
        domain = domain.lower().strip(".")
        if host == domain or host.endswith("." + domain):
            return "excluded domain"
    if host in ("github.com", "www.github.com", "raw.githubusercontent.com", "api.github.com"):
        for repo in config.excluded_repos:
            repo_path = "/" + repo.lower().strip("/")
            roots = (repo_path, "/repos" + repo_path)
            if any(path == root or path.startswith(root + "/") for root in roots):
                return "excluded repository"
    for pattern in config.excluded_paths:
        if fnmatch.fnmatch(path, pattern.lower()) or fnmatch.fnmatch(canonical_url(url).lower(), pattern.lower()):
            return "excluded path"
    return None


def filter_documents(documents, config):
    accepted, filtered = [], []
    urls, contents = set(), set()
    for doc in documents:
        reason = exclusion_reason(doc.url, config)
        url = canonical_url(doc.url)
        if not reason and (url in urls or doc.content_hash in contents):
            reason = "duplicate URL/content"
        if reason:
            filtered.append(FilteredResult(url=doc.url, reason=reason))
        elif len(accepted) < config.top_k:
            if doc.content_hash != digest(doc.text):
                raise RetrievalError("Document content hash mismatch")
            accepted.append(doc)
            urls.add(url)
            contents.add(doc.content_hash)
    return tuple(accepted), tuple(filtered)


class SnapshotStore:
    def __init__(self, config: Config, retriever: Retriever | None):
        self.config = config
        # REPLAY does not even retain a live adapter.
        self.retriever = retriever if config.mode == "LIVE" else None
        if config.mode == "LIVE" and retriever is None:
            raise ValueError("LIVE mode requires a retriever")
        self.config_hash = digest(
            {
                "version": PIPELINE_VERSION,
                "top_k": config.top_k,
                "search_depth": config.search_depth,
                "domains": config.excluded_domains,
                "repos": config.excluded_repos,
                "paths": config.excluded_paths,
            }
        )

    def get(self, query: SearchQuery):
        key = stable_id("snapshot", [self.config_hash, query.model_dump(mode="json")])
        path = self.config.cache_directory / f"{key}.json"
        if path.exists():
            return self._read(path, query, key)
        if self.config.mode == "REPLAY":
            raise RetrievalError(f"Missing frozen snapshot: {key}; no live fallback")
        try:
            docs = self.retriever.search(
                query.text, top_k=min(20, self.config.top_k * 2), timeout=self.config.retrieval_timeout
            )
        except requests.RequestException as exc:
            raise RetrievalError(f"Search transport: {type(exc).__name__}") from exc
        if any(d.query != query.text for d in docs):
            raise RetrievalError("Retriever returned documents for the wrong query")
        accepted, filtered = filter_documents(docs, self.config)
        snapshot = RetrievalSnapshot(
            snapshot_id=key,
            query=query,
            documents=accepted,
            filtered=filtered,
            config_hash=self.config_hash,
            provider=self.retriever.provider,
        )
        write_json(path, snapshot)
        return snapshot

    def _read(self, path: Path, query, key):
        snapshot = RetrievalSnapshot.model_validate_json(path.read_text(encoding="utf-8"))
        if snapshot.snapshot_id != key or snapshot.config_hash != self.config_hash or snapshot.query != query:
            raise RetrievalError("Snapshot configuration/query mismatch")
        if any(d.content_hash != digest(d.text) or d.query != query.text for d in snapshot.documents):
            raise RetrievalError("Snapshot content integrity failure")
        if any(exclusion_reason(d.url, self.config) for d in snapshot.documents):
            raise RetrievalError("Frozen evidence violates current leakage policy")
        return snapshot

    def read_by_id(self, snapshot_id):
        if not re.fullmatch(r"snapshot_[a-f0-9]{24}", snapshot_id):
            raise RetrievalError("Invalid snapshot ID")
        path = self.config.cache_directory / f"{snapshot_id}.json"
        if not path.exists():
            raise RetrievalError("Missing frozen snapshot")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            query = SearchQuery.model_validate(raw["query"])
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            raise RetrievalError("Malformed frozen snapshot") from exc
        return self._read(path, query, snapshot_id)
