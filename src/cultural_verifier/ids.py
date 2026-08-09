"""Canonical identifier validation and legacy-ID normalization."""

from __future__ import annotations

import re

DOMAIN_RE = re.compile(r"^D\d{2}$")
SUBDIMENSION_RE = re.compile(r"^D\d{2}S\d{2}$")
ATTACK_RE = re.compile(r"^AT\d{2}$")
PROMPT_RE = re.compile(r"^RT\d{3}$")
LEGACY_PROMPT_RE = re.compile(r"^LG\d{3}$")
PILOT_SET_RE = re.compile(r"^PLT\d{3}$")
CANDIDATE_RE = re.compile(r"^(?:RT\d{3}|PLT\d{3})-C[1-8]$")


def normalize_subdimension_id(value: str) -> str:
    """Convert historical IDs such as D01S1 to canonical D01S01."""
    match = re.fullmatch(r"D(\d{2})S(\d{1,2})", value.strip().upper())
    if not match:
        raise ValueError(f"Invalid subdimension ID: {value!r}")
    return f"D{int(match.group(1)):02d}S{int(match.group(2)):02d}"


def normalize_legacy_prompt_id(value: str) -> str:
    """Convert historical IDs such as G6 or G06 to canonical LG006."""
    match = re.fullmatch(r"(?:LG|G)(\d{1,3})", value.strip().upper())
    if not match:
        raise ValueError(f"Invalid legacy prompt ID: {value!r}")
    return f"LG{int(match.group(1)):03d}"


def candidate_id(set_or_prompt_id: str, position: int) -> str:
    if not 1 <= position <= 8:
        raise ValueError("Candidate position must be between 1 and 8")
    value = f"{set_or_prompt_id}-C{position}"
    if not CANDIDATE_RE.fullmatch(value):
        raise ValueError(f"Invalid candidate ID: {value!r}")
    return value


def require(pattern: re.Pattern[str], value: str, label: str) -> str:
    if not pattern.fullmatch(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value
