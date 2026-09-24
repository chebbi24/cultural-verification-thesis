"""Stateless provider adapters and bounded, schema-validated semantic calls."""

import json
from typing import Protocol
import requests
from pydantic import ValidationError
from .config import Config
from .prompts import COMMON, PROMPTS
from .schemas import CallRecord
from .trace import canonical, digest, timestamp


class StageError(RuntimeError):
    pass


class LLM(Protocol):
    config: Config

    def complete(self, *, stage: str, system: str, payload: dict, schema: dict) -> str: ...


class HTTPModel:
    """Each request has fresh messages. Never retains candidate conversation state."""

    def __init__(self, config: Config, api_key: str | None = None):
        if config.verifier_model_provider not in ("ollama", "openrouter"):
            raise ValueError("Supply a custom LLM adapter for provider=custom")
        if config.verifier_model_provider == "openrouter" and not api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
        self.config = config
        self._api_key = api_key

    def complete(self, *, stage, system, payload, schema):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": canonical(payload)}]
        if self.config.verifier_model_provider == "ollama":
            url = self.config.ollama_url
            body = {
                "model": self.config.verifier_model_id,
                "messages": messages,
                "format": schema,
                "think": False,
                "stream": False,
                "options": {"temperature": self.config.temperature},
            }
            headers = {}
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            body = {
                "model": self.config.verifier_model_id,
                "messages": messages,
                "temperature": self.config.temperature,
                "provider": {"require_parameters": True, "allow_fallbacks": False},
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": stage, "strict": True, "schema": strict_schema(schema)},
                },
            }
            headers = {"Authorization": f"Bearer {self._api_key}"}
        # Transport retries are handled by SemanticSession so every attempt is traced.
        response = requests.post(url, json=body, headers=headers, timeout=self.config.llm_timeout)
        response.raise_for_status()
        try:
            data = response.json()
            if self.config.verifier_model_provider == "ollama":
                content = data["message"]["content"]
            else:
                content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Missing textual structured output")
            return content
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise StageError("Malformed provider response envelope") from exc


def strict_schema(schema):
    """Convert tuple schemas to provider-compatible arrays; local validation stays exact."""
    result = json.loads(json.dumps(schema))

    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["required"] = list(node.get("properties", {}))
                node["additionalProperties"] = False
            if "prefixItems" in node:
                parts = node.pop("prefixItems")
                node["items"] = parts[0] if all(p == parts[0] for p in parts) else {"anyOf": parts}
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(result)
    return result


class SemanticSession:
    def __init__(self, llm: LLM, config: Config):
        if llm.config != config:
            raise ValueError("LLM and pipeline configuration must match exactly")
        self.llm = llm
        self.config = config
        self.calls = []

    def call(self, stage, payload, output_type, validator=None):
        if self.llm.config != self.config:
            raise StageError("Model configuration changed during run")
        # No chat history is retained or supplied to the LLM.
        payload = json.loads(canonical(payload))
        repair = ""
        attempt = 0
        for semantic_attempt in range(self.config.retry_count + 1):
            raw = None
            for transport_attempt in range(self.config.transport_retry_count + 1):
                attempt += 1
                try:
                    raw = self.llm.complete(
                        stage=stage,
                        system=COMMON + "\n" + PROMPTS[stage] + repair,
                        payload=payload,
                        schema=output_type.model_json_schema(),
                    )
                    break
                except StageError:
                    self.calls.append(
                        CallRecord(
                            stage=stage,
                            attempt=attempt,
                            timestamp=timestamp(),
                            input_hash=digest(payload),
                            output_json=None,
                            error="ProviderResponseError",
                        )
                    )
                    raise
                except requests.RequestException as exc:
                    status_code = (
                        exc.response.status_code
                        if isinstance(exc, requests.HTTPError) and exc.response is not None
                        else None
                    )
                    error_name = type(exc).__name__ + (f":{status_code}" if status_code is not None else "")
                    self.calls.append(
                        CallRecord(
                            stage=stage,
                            attempt=attempt,
                            timestamp=timestamp(),
                            input_hash=digest(payload),
                            output_json=None,
                            error=error_name,
                        )
                    )
                    retryable = isinstance(exc, (requests.Timeout, requests.ConnectionError)) or (
                        isinstance(exc, requests.HTTPError)
                        and status_code is not None
                        and (status_code == 429 or status_code >= 500)
                    )
                    if not retryable or transport_attempt == self.config.transport_retry_count:
                        suffix = f" status={status_code}" if status_code is not None else ""
                        raise StageError(f"{stage}: transport {type(exc).__name__}{suffix}") from exc
            try:
                value = output_type.model_validate_json(raw)
                if validator:
                    validator(value)
                self.calls.append(
                    CallRecord(
                        stage=stage,
                        attempt=attempt,
                        timestamp=timestamp(),
                        input_hash=digest(payload),
                        output_json=raw,
                        error=None,
                    )
                )
                return value
            except (ValidationError, ValueError, TypeError) as exc:
                self.calls.append(
                    CallRecord(
                        stage=stage,
                        attempt=attempt,
                        timestamp=timestamp(),
                        input_hash=digest(payload),
                        output_json=raw,
                        error=type(exc).__name__,
                    )
                )
                repair = (
                    "\nPrevious output was structurally invalid. Return JSON matching the supplied schema exactly. "
                    "Preserve exact spans or references only where that schema requires them. "
                )
                repair += str(exc)[:1500]
                if semantic_attempt == self.config.retry_count:
                    raise StageError(f"{stage}: invalid output after bounded retry") from exc
        raise StageError(f"{stage}: no output")
