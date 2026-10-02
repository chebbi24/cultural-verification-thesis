#!/usr/bin/env python3
"""Build a frozen 30x3 external cultural challenge set."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from datasets import load_dataset

SEED = "20261002"
OUT_VERSION = "external-challenge-30x3-v1"

VALUE_TERMS = {
    "family", "parent", "parents", "elder", "elders", "tradition", "traditional",
    "authority", "community", "religion", "religious", "marriage", "divorce",
    "gender", "women", "men", "education", "school", "work", "duty", "obligation",
    "equality", "inequality", "government", "leader", "leadership", "inheritance",
    "respect", "autonomy", "freedom", "social", "society", "moral", "values",
    "culture", "cultural", "ritual", "custom", "norm", "sexual", "lgbt", "violence",
    "children", "child", "youth", "care", "support", "responsibility",
}

PLURAL_COUNTRIES = ["Brazil", "India", "Japan", "Malaysia", "Zimbabwe"]


def stable_hash(*parts: Any) -> str:
    return hashlib.sha256("||".join(map(str, parts)).encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def challenge_score(prompt: str) -> int:
    p = (prompt or "").lower()
    score = sum(1 for term in VALUE_TERMS if term in p)
    score += 2 * len(re.findall(r"\b(but|however|while|versus|vs\.?|or|should|whether|instead)\b", p))
    if 120 <= len(prompt) <= 700:
        score += 3
    if "what do you think" in p or "how should" in p or "what should" in p:
        score += 2
    return score


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def select_plural() -> tuple[list[dict], list[dict]]:
    ds = load_dataset("agdhruv/plural-alignment", split="train", streaming=True)
    pools: dict[str, list[dict]] = defaultdict(list)

    for row in ds:
        country = row.get("country")
        if country not in PLURAL_COUNTRIES:
            continue
        prompt = str(row.get("prompt") or "").strip()
        pref = str(row.get("pref") or "").strip()
        dispref = str(row.get("dispref") or "").strip()
        if not (100 <= len(prompt) <= 900 and len(pref) >= 80 and len(dispref) >= 80):
            continue
        if word_count(pref) > 900 or word_count(dispref) > 900:
            continue

        meta = _as_dict(row.get("survey_metadata"))
        pools[country].append({
            "source": "PLURAL",
            "source_id": row.get("id"),
            "country": country,
            "region": row.get("region_iso"),
            "prompt": prompt,
            "preferred": pref,
            "dispreferred": dispref,
            "question_group_id": meta.get("question_group_id"),
            "question_group_codes": meta.get("question_group_codes"),
            "challenge_score": challenge_score(prompt),
        })

    selected: list[dict] = []
    for country in PLURAL_COUNTRIES:
        items = sorted(
            pools[country],
            key=lambda x: (-x["challenge_score"], stable_hash(SEED, x["source_id"])),
        )
        used_groups = set()
        country_sel = []
        for item in items:
            group_key = str(item.get("question_group_id"))
            if group_key in used_groups:
                continue
            country_sel.append(item)
            used_groups.add(group_key)
            if len(country_sel) == 6:
                break
        if len(country_sel) < 6:
            used_ids = {x["source_id"] for x in country_sel}
            for item in items:
                if item["source_id"] not in used_ids:
                    country_sel.append(item)
                    used_ids.add(item["source_id"])
                if len(country_sel) == 6:
                    break
        if len(country_sel) != 6:
            raise RuntimeError(f"PLURAL: expected 6 rows for {country}, got {len(country_sel)}")
        selected.extend(country_sel)

    blind, labels = [], []
    for i, item in enumerate(selected, 1):
        flip = int(stable_hash(SEED, item["source_id"])[0], 16) % 2
        a, b = ((item["preferred"], item["dispreferred"]) if flip == 0
                else (item["dispreferred"], item["preferred"]))
        evaluation_prompt = (
            f"Benchmark context: The user is from {item['country']}.\n\n"
            f"{item['prompt']}"
        )
        blind.append({
            "challenge_id": f"PLURAL{i:02d}",
            "source": "PLURAL",
            "source_id": item["source_id"],
            "country": item["country"],
            "region": item["region"],
            "prompt": evaluation_prompt,
            "original_prompt": item["prompt"],
            "candidate_A": a,
            "candidate_B": b,
            "selection_score": item["challenge_score"],
            "question_group_id": item["question_group_id"],
            "question_group_codes": json.dumps(item["question_group_codes"], ensure_ascii=False),
        })
        labels.append({
            "challenge_id": f"PLURAL{i:02d}",
            "source_id": item["source_id"],
            "preferred_candidate": "A" if flip == 0 else "B",
            "country": item["country"],
        })
    return blind, labels


def download_parquet(url: str, path: Path) -> pd.DataFrame:
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return pd.read_parquet(path)


def find_col(columns: list[str], candidates: list[str]) -> str | None:
    lower = {c.lower(): c for c in columns}
    for exact in candidates:
        if exact.lower() in lower:
            return lower[exact.lower()]
    for c in columns:
        lc = c.lower()
        if any(k.lower() in lc for k in candidates):
            return c
    return None


def normalize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, (list, tuple)):
        return "\n".join(str(v) for v in value)
    return str(value).strip()


def select_thaicli(tmp: Path) -> tuple[list[dict], list[dict], dict]:
    urls = {
        "factoid": "https://raw.githubusercontent.com/UpstageAI/ThaiCLI_H6/main/cli/CLI_factoid.parquet",
        "instruction": "https://raw.githubusercontent.com/UpstageAI/ThaiCLI_H6/main/cli/CLI_instruction.parquet",
    }
    frames = []
    schema_info = {}
    for fmt, url in urls.items():
        df = download_parquet(url, tmp / f"thai_{fmt}.parquet")
        df["_format"] = fmt
        frames.append(df)
        schema_info[fmt] = {"columns": list(df.columns), "rows": int(len(df))}
    df = pd.concat(frames, ignore_index=True)

    cols = list(df.columns)
    qcol = find_col(cols, ["question", "prompt", "instruction", "query"])
    ccol = find_col(cols, ["chosen", "chosen_answer", "accepted", "preferred"])
    rcol = find_col(cols, ["rejected", "rejected_answer", "dispreferred"])
    acol = "answers" if "answers" in cols else None
    theme_col = find_col(cols, ["theme", "category", "topic", "domain"])
    id_col = find_col(cols, ["id", "index", "qid", "question_id"])
    if not qcol or (not acol and not (ccol and rcol)):
        sample_answers = repr(df["answers"].iloc[0]) if "answers" in df.columns and len(df) else "<none>"
        raise RuntimeError(
            f"ThaiCLI schema unsupported. columns={cols}; inferred q={qcol}, chosen={ccol}, rejected={rcol}; "
            f"sample answers={sample_answers}"
        )

    items = []
    for idx, row in df.iterrows():
        q = normalize_cell(row[qcol])
        if acol:
            raw_answers = row[acol]
            entries = list(raw_answers) if raw_answers is not None else []
            chosen_entries = [
                x for x in entries
                if isinstance(x, dict) and int(x.get("score", -1)) == 1
            ]
            rejected_entries = [
                x for x in entries
                if isinstance(x, dict) and int(x.get("score", -1)) == 0
            ]
            chosen = normalize_cell(chosen_entries[0].get("content")) if chosen_entries else ""
            rejected = normalize_cell(rejected_entries[0].get("content")) if rejected_entries else ""
        else:
            chosen = normalize_cell(row[ccol])
            rejected = normalize_cell(row[rcol])
        if not q or len(chosen) < 20 or len(rejected) < 20:
            continue
        fmt = row["_format"]
        theme = normalize_cell(row[theme_col]) if theme_col else "unknown"
        sid = normalize_cell(row[id_col]) if id_col else f"{fmt}_{idx}"
        ratio = min(len(chosen), len(rejected)) / max(len(chosen), len(rejected), 1)
        score = challenge_score(q) + (4 if fmt == "instruction" else 1) + (2 if ratio >= 0.45 else 0)
        items.append({
            "source_id": sid,
            "format": fmt,
            "theme": theme or "unknown",
            "prompt": q,
            "chosen": chosen,
            "rejected": rejected,
            "challenge_score": score,
        })

    items = sorted(items, key=lambda x: (-x["challenge_score"], stable_hash(SEED, x["source_id"])))
    selected = []
    theme_counts: dict[str, int] = defaultdict(int)
    format_counts: dict[str, int] = defaultdict(int)
    for item in items:
        theme = item["theme"]
        if theme_counts[theme] >= 6:
            continue
        if item["format"] == "factoid" and format_counts["factoid"] >= 18:
            continue
        if item["format"] == "instruction" and format_counts["instruction"] >= 15:
            continue
        selected.append(item)
        theme_counts[theme] += 1
        format_counts[item["format"]] += 1
        if len(selected) == 30:
            break
    if len(selected) < 30:
        used = {x["source_id"] for x in selected}
        for item in items:
            if item["source_id"] not in used:
                selected.append(item)
                used.add(item["source_id"])
            if len(selected) == 30:
                break
    if len(selected) != 30:
        raise RuntimeError(f"ThaiCLI: expected 30 rows, got {len(selected)}")

    blind, labels = [], []
    for i, item in enumerate(selected, 1):
        flip = int(stable_hash(SEED, "thai", item["source_id"])[0], 16) % 2
        a, b = ((item["chosen"], item["rejected"]) if flip == 0
                else (item["rejected"], item["chosen"]))
        blind.append({
            "challenge_id": f"THAI{i:02d}",
            "source": "ThaiCLI",
            "source_id": item["source_id"],
            "country": "Thailand",
            "format": item["format"],
            "theme": item["theme"],
            "prompt": item["prompt"],
            "candidate_A": a,
            "candidate_B": b,
            "selection_score": item["challenge_score"],
        })
        labels.append({
            "challenge_id": f"THAI{i:02d}",
            "source_id": item["source_id"],
            "chosen_candidate": "A" if flip == 0 else "B",
            "format": item["format"],
            "theme": item["theme"],
        })
    schema_info["inferred"] = {
        "question_col": qcol, "chosen_col": ccol, "rejected_col": rcol, "answers_col": acol,
        "theme_col": theme_col, "id_col": id_col,
        "selected_theme_counts": dict(theme_counts),
        "selected_format_counts": dict(format_counts),
    }
    return blind, labels, schema_info


def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        # The released CSV stores valid JSON in normal rows; fail closed if a row is malformed.
        return {}


def normalize_culture(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


def disco_score(question: str, options: dict[str, Any]) -> int:
    q = (question or "").lower()
    opts = " ".join(map(str, options.values())).lower()
    social_terms = {
        "family", "parent", "parents", "elder", "elders", "gift", "wedding",
        "marriage", "birthday", "funeral", "friend", "friends", "celebrate",
        "celebration", "holiday", "festival", "visit", "visiting", "guest",
        "children", "school", "salary", "recreation", "weekend", "party",
        "meal", "drink", "eat", "food", "leisure", "home",
    }
    trivia_terms = {
        "capital", "export", "corporation", "company", "population", "currency",
        "largest", "famous public", "national animal", "flag",
    }
    score = 3 * sum(1 for t in social_terms if t in q)
    score += sum(1 for t in social_terms if t in opts)
    score -= 3 * sum(1 for t in trivia_terms if t in q)
    if 25 <= len(question) <= 180:
        score += 2
    return score


def select_disco() -> tuple[list[dict], list[dict], dict]:
    url = (
        "https://huggingface.co/datasets/DiSCo2026/DiSCo_Dataset_and_Benchmark/"
        "resolve/main/DiSCo%20Bench.csv?download=true"
    )
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    from io import StringIO
    df = pd.read_csv(StringIO(resp.text))

    required = {
        "QID", "ID", "Question", "Options", "Metadata",
        "User_Info", "User_Instruction",
    }
    if not required.issubset(df.columns):
        raise RuntimeError(f"DiSCo schema mismatch: {list(df.columns)}")

    items = []
    for _, row in df.iterrows():
        options = parse_json_object(row["Options"])
        mapping = parse_json_object(row["Metadata"])
        if set(options) != {"A", "B", "C", "D"} or set(mapping) != {"A", "B", "C", "D"}:
            continue
        user_info = str(row["User_Info"] or "").strip()
        m = re.search(r"located in\s+(.+?)[.]?$", user_info, flags=re.I)
        if not m:
            continue
        target = m.group(1).strip()
        target_norm = normalize_culture(target)

        correct = [
            letter for letter, culture in mapping.items()
            if normalize_culture(str(culture)) == target_norm
        ]
        if len(correct) != 1:
            continue

        question = str(row["Question"]).strip()
        prompt = (
            f"{user_info}\n"
            f"{str(row['User_Instruction']).strip()}\n\n"
            f"{question}"
        )
        items.append({
            "source_id": str(row["ID"]),
            "qid": str(row["QID"]),
            "culture": target,
            "question": question,
            "prompt": prompt,
            "options": {k: str(v) for k, v in options.items()},
            "mapping": {k: str(v) for k, v in mapping.items()},
            "correct": correct[0],
            "challenge_score": disco_score(question, options),
        })

    by_culture: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        by_culture[item["culture"]].append(item)
    cultures = sorted(by_culture)
    if len(cultures) < 12:
        raise RuntimeError(f"DiSCo: expected 12 cultures, found {cultures}")

    for culture in cultures:
        by_culture[culture].sort(
            key=lambda x: (
                -x["challenge_score"],
                stable_hash(SEED, "disco", culture, x["source_id"]),
            )
        )

    # 2 per culture = 24, plus one extra for six cultures selected deterministically.
    extras = set(
        sorted(cultures, key=lambda x: stable_hash(SEED, "disco-extra", x))[:6]
    )
    selected = []
    for culture in cultures:
        n = 3 if culture in extras else 2
        selected.extend(by_culture[culture][:n])
    if len(selected) != 30:
        raise RuntimeError(f"DiSCo: expected 30 rows, got {len(selected)}")

    # Global deterministic ID order after culture-balanced selection.
    selected.sort(key=lambda x: (x["culture"], x["source_id"]))

    blind, labels = [], []
    for i, item in enumerate(selected, 1):
        row = {
            "challenge_id": f"DISCO{i:02d}",
            "source": "DiSCo-Bench",
            "source_id": item["source_id"],
            "qid": item["qid"],
            "country": item["culture"],
            "prompt": item["prompt"],
            "original_question": item["question"],
            "selection_score": item["challenge_score"],
        }
        for letter in ("A", "B", "C", "D"):
            row[f"candidate_{letter}"] = item["options"][letter]
        blind.append(row)
        labels.append({
            "challenge_id": f"DISCO{i:02d}",
            "source_id": item["source_id"],
            "target_culture": item["culture"],
            "locally_mapped_candidate": item["correct"],
            "culture_mapping": item["mapping"],
        })

    info = {
        "benchmark_rows_read": int(len(df)),
        "eligible_rows": len(items),
        "cultures": cultures,
        "extra_item_cultures": sorted(extras),
        "selection_note": (
            "C2-style prompt: exact User_Info + exact User_Instruction + Question; "
            "candidates are the four exact released option texts. Hidden Metadata mapping "
            "is stored only in the reference-label file."
        ),
    }
    return blind, labels, info

def write_txt(path: Path, plural: list[dict], thai: list[dict], disco: list[dict]) -> None:
    lines = [
        "VERICULT EXTERNAL CULTURAL CHALLENGE SET — BLINDED",
        f"Version: {OUT_VERSION}",
        f"Selection seed: {SEED}",
        "",
        "IMPORTANT:",
        "- Selected before any Vericult output is inspected.",
        "- Candidate order is deterministic and label-blinded.",
        "- PLURAL and ThaiCLI contain two candidates; DiSCo-Bench contains four culturally grounded options.",
        "- Source preference/mapping labels are stored separately and MUST NOT be supplied to Vericult.",
        "",
    ]
    for title, rows in [
        ("SOURCE 1 — PLURAL (30)", plural),
        ("SOURCE 2 — ThaiCLI (30)", thai),
        ("SOURCE 3 — DiSCo-Bench (30)", disco),
    ]:
        lines.extend(["=" * 88, title, "=" * 88, ""])
        for row in rows:
            lines.append(row["challenge_id"])
            lines.append(f"Source ID: {row.get('source_id')}")
            lines.append(f"Country: {row.get('country')}")
            for key in ("region", "format", "theme", "tier", "framing", "language"):
                if row.get(key) not in (None, "", "nan"):
                    lines.append(f"{key.title()}: {row.get(key)}")
            lines.extend(["", "PROMPT:", row["prompt"], ""])
            for letter in ("A", "B", "C", "D"):
                key = f"candidate_{letter}"
                if key in row and row[key]:
                    model = row.get(f"model_{letter}")
                    hdr = f"CANDIDATE {letter}" + (f" [published model: {model}]" if model else "")
                    lines.extend([hdr + ":", row[key], ""])
            lines.extend(["-" * 88, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", default="data/external_challenge")
    args = ap.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_tmp"
    tmp.mkdir(exist_ok=True)

    thai, thai_labels, thai_info = select_thaicli(tmp)
    disco, disco_labels, disco_info = select_disco()
    plural, plural_labels = select_plural()

    pd.DataFrame(plural).to_csv(out / "plural_30_blind.csv", index=False)
    pd.DataFrame(thai).to_csv(out / "thaicli_30_blind.csv", index=False)
    pd.DataFrame(disco).to_csv(out / "disco_30_blind.csv", index=False)

    labels = {
        "version": OUT_VERSION,
        "selection_seed": SEED,
        "plural": plural_labels,
        "thaicli": thai_labels,
        "disco": disco_labels,
    }
    (out / "reference_labels_DO_NOT_FEED_VERICULT.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    info = {
        "version": OUT_VERSION,
        "selection_seed": SEED,
        "selection_policy": {
            "no_vericult_outputs_used": True,
            "plural": "6 items per released country; maximize question-group diversity; rank prompt-only red-team score.",
            "thaicli": "theme/format-stratified; instruction cases prioritized; no Vericult use.",
            "disco": "30 C2-style DiSCo-Bench items; balance all 12 cultures; rank prompt/options only; hidden culture mapping excluded from selection.",
        },
        "source_releases": {
            "plural": "agdhruv/plural-alignment current HF default release at run time",
            "thaicli": "UpstageAI/ThaiCLI_H6 main",
            "disco": "DiSCo2026/DiSCo_Dataset_and_Benchmark — DiSCo Bench.csv",
        },
        "counts": {"plural": len(plural), "thaicli": len(thai), "disco": len(disco)},
        "thaicli_schema": thai_info,
        "disco_info": disco_info,
    }
    (out / "selection_manifest.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_txt(out / "external_challenge_90_blind.txt", plural, thai, disco)

    for p in tmp.glob("*"):
        p.unlink()
    tmp.rmdir()

    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
