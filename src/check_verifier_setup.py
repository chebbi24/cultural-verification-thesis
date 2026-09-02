"""Fail-fast setup checks for supported cultural-verifier backends."""

from __future__ import annotations

import argparse
import os
import sys

import requests

from verifier import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENROUTER_MODEL,
    OLLAMA_LOCAL_CHAT_URL,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("ollama", "openrouter"), default="ollama")
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--search-provider", choices=("same", "openrouter"), default="same"
    )
    parser.add_argument("--search-model", default=None)
    parser.add_argument(
        "--require-web-search",
        action="store_true",
        help="For the Ollama backend, require OLLAMA_API_KEY for hosted web search.",
    )
    args = parser.parse_args()

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
        str(item.get("name", "")).strip()
        for item in response.json().get("models", [])
        if isinstance(item, dict)
    }
    if model not in installed:
        print(f"FAIL local model missing: {model}")
        print(f"Run: ollama pull {model}")
        sys.exit(1)
    print(f"OK local Ollama server and model: {model}")

    if args.search_provider == "openrouter":
        print("OK local Ollama judge will route evidence calls through OpenRouter")
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
