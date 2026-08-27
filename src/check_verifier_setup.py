"""Fail-fast setup checks for the local Ollama cultural-verifier backend."""

from __future__ import annotations

import argparse
import os
import sys

import requests

from verifier import DEFAULT_OLLAMA_MODEL, OLLAMA_LOCAL_CHAT_URL


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    parser.add_argument(
        "--require-web-search",
        action="store_true",
        help="Require OLLAMA_API_KEY, which the full evidence-grounded verifier needs.",
    )
    args = parser.parse_args()

    tags_url = OLLAMA_LOCAL_CHAT_URL.rsplit("/api/chat", 1)[0] + "/api/tags"
    try:
        response = requests.get(tags_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"FAIL local Ollama server: {exc}")
        print("Start Ollama, then run: ollama pull " + args.model)
        sys.exit(1)

    installed = {
        str(item.get("name", "")).strip()
        for item in response.json().get("models", [])
        if isinstance(item, dict)
    }
    if args.model not in installed:
        print(f"FAIL local model missing: {args.model}")
        print(f"Run: ollama pull {args.model}")
        sys.exit(1)
    print(f"OK local Ollama server and model: {args.model}")

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
