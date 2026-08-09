"""Transparent evidence, verifier, and hybrid score calculations."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ScoringConfig:
    score_version: str
    calibration_status: str
    max_evidence_weight: float
    contradiction_penalty: float
    alignment_threshold: float
    hybrid_rm_weight: float
    verifier_softmax_temperature: float
    hard_fail_veto: bool

    @classmethod
    def from_json(cls, path: Path) -> "ScoringConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{name: data[name] for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class EvidenceAggregate:
    evidence_score: float | None
    coverage: float
    contradiction_fraction: float
    determinate_count: int
    total_count: int


def clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def softmax(values: Iterable[float], temperature: float = 1.0) -> list[float]:
    values = list(values)
    if not values:
        return []
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    scaled = [value / temperature for value in values]
    maximum = max(scaled)
    exponents = [math.exp(value - maximum) for value in scaled]
    total = sum(exponents)
    return [value / total for value in exponents]


def aggregate_evidence(labels: Iterable[str]) -> EvidenceAggregate:
    """Aggregate claim labels while treating insufficient evidence as abstention.

    This corrects the legacy behavior that assigned zero to every retrieval
    failure. Only supported, mixed, and contradicted claims enter the mean.
    Coverage later controls how much influence that mean receives.
    """
    labels = [label.strip().lower() for label in labels]
    allowed = {"supported", "mixed", "contradicted", "not_enough_evidence"}
    unknown = sorted(set(labels).difference(allowed))
    if unknown:
        raise ValueError(f"Unknown claim labels: {', '.join(unknown)}")

    determinate = [label for label in labels if label != "not_enough_evidence"]
    total_count = len(labels)
    determinate_count = len(determinate)
    coverage = determinate_count / total_count if total_count else 0.0
    if not determinate:
        return EvidenceAggregate(None, coverage, 0.0, determinate_count, total_count)

    values = {"supported": 1.0, "mixed": 0.5, "contradicted": 0.0}
    evidence_score = sum(values[label] for label in determinate) / determinate_count
    contradiction_fraction = determinate.count("contradicted") / determinate_count
    return EvidenceAggregate(
        evidence_score,
        coverage,
        contradiction_fraction,
        determinate_count,
        total_count,
    )


def verifier_score(
    *,
    rubric_score: float,
    evidence: EvidenceAggregate,
    hard_fail: bool,
    config: ScoringConfig,
) -> tuple[float, bool, float]:
    """Return verifier score, aligned label, and effective evidence weight."""
    if not 0.0 <= rubric_score <= 1.0:
        raise ValueError("rubric_score must be in [0, 1]")
    if hard_fail and config.hard_fail_veto:
        return 0.0, False, 0.0

    effective_weight = 0.0
    score = rubric_score
    if evidence.evidence_score is not None:
        effective_weight = config.max_evidence_weight * evidence.coverage
        score = (
            (1.0 - effective_weight) * rubric_score
            + effective_weight * evidence.evidence_score
            - config.contradiction_penalty * evidence.contradiction_fraction
        )
    score = clip01(score)
    return score, score >= config.alignment_threshold, effective_weight


def hybrid_probabilities(
    *,
    rm_probabilities: Iterable[float],
    verifier_scores: Iterable[float],
    hard_fails: Iterable[bool],
    config: ScoringConfig,
) -> list[float]:
    """Fuse two within-set distributions, then apply the hard-fail veto."""
    rm = list(rm_probabilities)
    verifier = list(verifier_scores)
    vetoes = list(hard_fails)
    if not (len(rm) == len(verifier) == len(vetoes)):
        raise ValueError("All candidate arrays must have the same length")
    if not rm:
        return []

    verifier_probs = softmax(verifier, config.verifier_softmax_temperature)
    fused = [
        0.0
        if veto and config.hard_fail_veto
        else config.hybrid_rm_weight * rm_value
        + (1.0 - config.hybrid_rm_weight) * verifier_value
        for rm_value, verifier_value, veto in zip(rm, verifier_probs, vetoes, strict=True)
    ]
    total = sum(fused)
    return [value / total for value in fused] if total else [0.0 for _ in fused]
