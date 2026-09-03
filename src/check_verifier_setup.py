"""Fail-fast setup checks for supported cultural-verifier backends."""

from __future__ import annotations

import argparse
import os
import sys

import requests

from verifier import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_TAVILY_SEARCH_DEPTH,
    OLLAMA_LOCAL_CHAT_URL,
    TAVILY_SEARCH_URL,
    OllamaClient,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("ollama", "openrouter"), default="ollama")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--search-provider",
        choices=("same", "tavily", "openrouter"),
        default="tavily",
    )
    parser.add_argument("--search-model", default=None)
    parser.add_argument(
        "--search-depth", choices=("basic", "advanced"), default=None
    )
    parser.add_argument(
        "--require-web-search",
        action="store_true",
        help="For the Ollama backend, require OLLAMA_API_KEY for hosted web search.",
    )
    parser.add_argument("--ollama-timeout", type=float, default=None)
    parser.add_argument("--ollama-attempts", type=int, default=None)
    parser.add_argument(
        "--skip-judge-smoke",
        action="store_true",
        help="Check installation only; do not run one structured local-model request.",
    )
    args = parser.parse_args()

    if args.search_provider == "tavily":
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        if not api_key:
            print("FAIL TAVILY_API_KEY is missing.")
            print('Run: export TAVILY_API_KEY="..."')
            sys.exit(1)
        depth = args.search_depth or DEFAULT_TAVILY_SEARCH_DEPTH
        try:
            response = requests.post(
                TAVILY_SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": "Germany cultural context verifier setup test",
                    "topic": "general",
                    "search_depth": depth,
                    "max_results": 1,
                    "include_answer": False,
                    "include_raw_content": False,
                    "include_images": False,
                },
                timeout=20,
            )
            response.raise_for_status()
            result_count = len(response.json().get("results") or [])
        except (requests.RequestException, ValueError) as exc:
            print(f"FAIL Tavily search validation: {exc}")
            sys.exit(1)
        print(
            f"OK Tavily Search API: depth={depth}, results={result_count}; "
            "ranking model=proprietary/not publicly identified"
        )

    if args.backend == "openrouter" or args.search_provider == "openrouter":
        openrouter_model = (
            args.model if args.backend == "openrouter" else args.search_model
        ) or DEFAULT_OPENROUTER_MODEL
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            print("FAIL OPENROUTER_API_KEY is missing.")
            print('Run: export OPENROUTER_API_KEY="..."')
            sys.exit(1)
        try:
            response = requests.get(
                "https://openrouter.ai/api/v1/key",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"FAIL OpenRouter API-key validation: {exc}")
            sys.exit(1)
        key_data = response.json().get("data") or {}
        remaining = key_data.get("limit_remaining")
        remaining_text = "unknown" if remaining is None else str(remaining)
        print(f"OK OpenRouter API key accepted; remaining limit: {remaining_text}")
        print(f"OK OpenRouter model: {openrouter_model}")
        print("OK OpenRouter web retrieval uses the web plugin when evidence is required")
        if args.backend == "openrouter":
            return

    model = args.model or DEFAULT_OLLAMA_MODEL

    tags_url = OLLAMA_LOCAL_CHAT_URL.rsplit("/api/chat", 1)[0] + "/api/tags"
    try:
        response = requests.get(tags_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"FAIL local Ollama server: {exc}")
        print("Start Ollama, then run: ollama pull " + model)
        sys.exit(1)

    installed = {
        str(item.get("name", "")).strip(): item
        for item in response.json().get("models", [])
        if isinstance(item, dict)
    }
    if model not in installed:
        print(f"FAIL local model missing: {model}")
        print(f"Run: ollama pull {model}")
        sys.exit(1)
    digest = str(installed[model].get("digest", "")).strip() or "not reported"
    print(f"OK local Ollama server and model: {model}; digest={digest}")

    if not args.skip_judge_smoke:
        smoke_schema = {
            "type": "object",
            "properties": {"status": {"type": "string", "enum": ["ready"]}},
            "required": ["status"],
            "additionalProperties": False,
        }
        try:
            data, _ = OllamaClient(
                model=model,
                timeout_seconds=args.ollama_timeout,
                max_attempts=args.ollama_attempts,
            ).json_call(
                "Return JSON only with status set to ready.",
                {"task": "verifier setup smoke test"},
                response_schema=smoke_schema,
                schema_name="setup_smoke",
            )
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            print(f"FAIL local Ollama structured-output smoke test: {exc}")
            sys.exit(1)
        print(f"OK local Ollama structured output: {data['status']}")

    if args.search_provider in {"openrouter", "tavily"}:
        provider_name = "OpenRouter" if args.search_provider == "openrouter" else "Tavily"
        print(f"OK local Ollama judge will evaluate {provider_name} evidence")
        return

    has_web_key = bool(os.getenv("OLLAMA_API_KEY"))
    if has_web_key:
        print("OK OLLAMA_API_KEY is set for hosted web search")
    elif args.require_web_search:
        print("FAIL OLLAMA_API_KEY is missing; evidence retrieval cannot run.")
        print('Run: export OLLAMA_API_KEY="..."')
        sys.exit(1)
    else:
        print("WARN OLLAMA_API_KEY is absent; schema smoke tests work, evidence retrieval does not.")


if __name__ == "__main__":
    main()
