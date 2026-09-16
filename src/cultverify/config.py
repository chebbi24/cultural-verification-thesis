from pathlib import Path
from typing import Literal
from pydantic import Field
from .schemas import Record

PIPELINE_VERSION = "cultverify-1.0.0"


class Config(Record):
    verifier_model_provider: Literal["ollama", "openrouter", "custom"] = "ollama"
    verifier_model_id: str = Field(min_length=1)  # Deliberate experimental choice, no silent default.
    temperature: float = Field(default=0, ge=0, le=2)
    retry_count: int = Field(default=1, ge=0, le=1)
    transport_retry_count: int = Field(default=1, ge=0, le=3)
    llm_timeout: float = Field(default=180, gt=0)
    retrieval_timeout: float = Field(default=45, gt=0)
    top_k: int = Field(default=3, ge=1, le=20)
    max_material_targets: int = Field(default=3, ge=1, le=3)
    max_retrieval_rounds: int = Field(default=2, ge=1, le=2)
    mode: Literal["LIVE", "REPLAY"] = "LIVE"
    cache_directory: Path = Path("artifacts/evidence")
    trace_directory: Path = Path("artifacts/traces")
    ollama_url: str = "http://localhost:11434/api/chat"
    search_depth: Literal["basic", "advanced"] = "advanced"
    excluded_domains: tuple[str, ...] = ()
    excluded_repos: tuple[str, ...] = ("chebbi24/cultural-verification-thesis",)
    excluded_paths: tuple[str, ...] = (
        "*/annotations/*",
        "*/results/*",
        "*human_label*",
        "*silver_label*",
        "*provisional_annotations*",
    )
