"""Compare Docling_OCR_new output with the saved Azure OCR for the same pages.

    python compare.py

Reads output/<folder>/<image>.json (from run.py) and Data/OCR_Output/**/*.json,
matches pages by file name, and writes output/comparison.csv plus a printed table.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
from collections import Counter
from pathlib import Path

import config

AZURE_DIR = Path(config.DATA_RAW_DIR).parent / "OCR_Output"
INPUT_CSV = Path(config.DATA_RAW_DIR).parent / "system_input.csv"


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def box(polygon: list[float], sx: float, sy: float) -> tuple[float, float, float, float]:
    xs, ys = polygon[0::2], polygon[1::2]
    return min(xs) * sx, min(ys) * sy, max(xs) * sx, max(ys) * sy


def iou(a: tuple, b: tuple) -> float:
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = w * h
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def load_azure() -> dict[str, dict]:
    pages: dict[str, dict] = {}
    for path in AZURE_DIR.rglob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for page in doc.get("pages", []):
            pages[(path.parent.name.casefold(), Path(page["fileName"]).stem)] = {"page": page, "recordId": doc.get("recordId")}
    return pages


def load_records() -> dict[str, dict]:
    with INPUT_CSV.open(encoding="utf-8-sig", newline="") as fh:
        return {row["RecordId"]: row for row in csv.DictReader(fh)}


def compare_page(docling: dict, azure: dict) -> dict:
    d_words, a_words = docling["words"], azure["words"]
    d_sx = azure["width"] / docling["width"]
    d_sy = azure["height"] / docling["height"]

    d_tokens = Counter(norm(w["content"]) for w in d_words if norm(w["content"]))
    a_tokens = Counter(norm(w["content"]) for w in a_words if norm(w["content"]))
    shared = sum((d_tokens & a_tokens).values())

    # Each Docling word is paired with the unused Azure word of the same text
    # whose box is closest; IoU is measured on those pairs.
    used: set[int] = set()
    ious: list[float] = []
    for dw in d_words:
        key = norm(dw["content"])
        if not key:
            continue
        db = box(dw["polygon"], d_sx, d_sy)
        best, best_i = None, -1.0
        for i, aw in enumerate(a_words):
            if i in used or norm(aw["content"]) != key:
                continue
            score = iou(db, box(aw["polygon"], 1, 1))
            if score > best_i:
                best, best_i = i, score
        if best is not None:
            used.add(best)
            ious.append(best_i)

    text_ratio = difflib.SequenceMatcher(
        None, norm(docling["content"]), norm(azure["content"]), autojunk=False
    ).ratio()
    return {
        "docling_words": len(d_words),
        "azure_words": len(a_words),
        "shared_tokens": shared,
        "recall_vs_azure": round(shared / max(sum(a_tokens.values()), 1), 3),
        "precision_vs_azure": round(shared / max(sum(d_tokens.values()), 1), 3),
        "text_similarity": round(text_ratio, 3),
        "matched_pairs": len(ious),
        "mean_iou": round(sum(ious) / len(ious), 3) if ious else 0.0,
        "iou_ge_0.5": round(sum(1 for v in ious if v >= 0.5) / len(ious), 3) if ious else 0.0,
        "azure_only": [w for w, _ in (a_tokens - d_tokens).most_common(8)],
        "docling_only": [w for w, _ in (d_tokens - a_tokens).most_common(8)],
    }


def main() -> None:
    azure_pages = load_azure()
    records = load_records()
    rows = []
    for path in sorted(Path(config.OUTPUT_DIR).glob("*/*.json")):
        docling = json.loads(path.read_text(encoding="utf-8"))
        entry = azure_pages.get((path.parent.name.casefold(), path.stem))
        if entry is None:
            print(f"no Azure page for {path.name}")
            continue
        row = {"folder": path.parent.name, "image": path.stem, "record": entry["recordId"]}
        row.update(compare_page(docling, entry["page"]))
        member = (records.get(entry["recordId"]) or {}).get("MemberID", "")
        if member and member != "N/A":
            row["member_id_in_docling"] = norm(member) in norm(docling["content"])
            row["member_id_in_azure"] = norm(member) in norm(entry["page"]["content"])
        rows.append(row)

    out = Path(config.OUTPUT_DIR) / "comparison.csv"
    fields = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows({k: (" ".join(v) if isinstance(v, list) else v) for k, v in r.items()} for r in rows)
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    print("->", out)


if __name__ == "__main__":
    main()

