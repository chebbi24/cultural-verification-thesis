"""Small JSON-producing CLI; no benchmark metadata is accepted."""

import argparse
import json
import os
import sys
from pathlib import Path
from .config import Config
from .llm import HTTPModel
from .pipeline import CulturalVerifier
from .retrieval import TavilyRetriever


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "rank"):
        command = sub.add_parser(name)
        prompt = command.add_mutually_exclusive_group(required=True)
        prompt.add_argument("--prompt")
        prompt.add_argument("--prompt-file", type=Path)
        if name == "verify":
            response = command.add_mutually_exclusive_group(required=True)
            response.add_argument("--response")
            response.add_argument("--response-file", type=Path)
        else:
            command.add_argument(
                "--responses-file", required=True, type=Path, help="JSON array of exactly four strings"
            )
        command.add_argument("--config", type=Path, help="Config JSON, credentials excluded")
        command.add_argument("--model")
        command.add_argument("--provider", choices=("ollama", "openrouter"))
        command.add_argument("--mode", choices=("LIVE", "REPLAY"))
        command.add_argument("--cache-directory", type=Path)
        command.add_argument("--trace-directory", type=Path)
    args = parser.parse_args(argv)
    try:
        values = json.loads(args.config.read_text()) if args.config else {}
        env = {
            "verifier_model_id": "CULTVERIFY_MODEL",
            "verifier_model_provider": "CULTVERIFY_PROVIDER",
            "mode": "CULTVERIFY_MODE",
            "ollama_url": "OLLAMA_URL",
        }
        for key, name in env.items():
            if name in os.environ:
                values[key] = os.environ[name]
        for arg, key in [
            ("model", "verifier_model_id"),
            ("provider", "verifier_model_provider"),
            ("mode", "mode"),
            ("cache_directory", "cache_directory"),
            ("trace_directory", "trace_directory"),
        ]:
            if getattr(args, arg) is not None:
                values[key] = getattr(args, arg)
        config = Config.model_validate(values)
        llm = HTTPModel(config, os.getenv("OPENROUTER_API_KEY"))
        retriever = TavilyRetriever(os.getenv("TAVILY_API_KEY"), config.search_depth) if config.mode == "LIVE" else None
        verifier = CulturalVerifier(llm=llm, retriever=retriever, config=config)
        prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else args.prompt
        if args.command == "verify":
            response = args.response_file.read_text(encoding="utf-8") if args.response_file else args.response
            result = verifier.verify(prompt=prompt, response=response)
            failed = result.status == "failed"
        else:
            responses = json.loads(args.responses_file.read_text(encoding="utf-8"))
            if not isinstance(responses, list) or not all(isinstance(r, str) for r in responses):
                raise ValueError("Responses file must contain a JSON array of strings")
            result = verifier.rank(prompt=prompt, responses=responses)
            failed = any(c.status == "failed" for c in result.candidates)
        print(result.model_dump_json(indent=2))
        return 2 if failed else 0
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
