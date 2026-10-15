"""Two unreviewed runs of the same records scored against a reviewed run: what the new one gained and lost.

    python Training/compare_runs.py --reviewed KV_Run_A --base KV_Run_B --new KV_Run_C

--reviewed  the run whose reviews are the truth (its labels are matched to the other runs' candidates
            by candidate id / same value at the same words, like Training/dataset.py)
--base      a rerun of the same records with the version being compared against (e.g. v004)
--new       a rerun with the experimental version (e.g. v005)

Per field: what each run selected, how many of those were true (TP) or false (FP), true candidates
it missed (FN), precision / recall, and what changed between the two. Written next to the new run's
tables (never inside KV_Extraction, so the Review UI and the trainer never read it):
    {new run}/Compare_vs_{base run}.csv           one row per field
    {new run}/Compare_vs_{base run}_changes.csv   every candidate selected in one run and not the other
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from Training.dataset import build
from Training.features import run_selected
from Util import config
from Util.geometry import is_edge_region


def _run_dir(name: str) -> Path:
    path = Path(name)
    return path if path.is_dir() else config.Run_Output / name


def _labelled(reviewed: str, run: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(that run's candidates with a 0/1 label on every reviewed page, generator misses)."""
    frame, misses, _ = build([reviewed, run])
    if frame.empty:
        raise SystemExit(f"{run}: no candidates on pages {reviewed} reviewed")
    frame = frame[frame["is_placeholder"].astype(str) != "1"].copy()
    frame["selected_now"] = [run_selected(row) for row in frame.to_dict("records")]
    return frame, misses


def _field_row(label: str, field: str, frame: pd.DataFrame, misses: pd.DataFrame) -> dict:
    rows = frame[frame["field"] == field]
    selected = rows[rows["selected_now"]]
    true_sel = int((selected["label"] == 1).sum())
    false_sel = int((selected["label"] == 0).sum())
    positives = int((rows["label"] == 1).sum()) + int((misses["field"] == field).sum())
    edge = pd.Series([is_edge_region(str(region)) for region in selected["region"]], index=selected.index, dtype=bool)
    edge &= ~selected["field"].isin(["headings", "heading_heron"])
    precision = true_sel / (true_sel + false_sel) if true_sel + false_sel else float("nan")
    recall = true_sel / positives if positives else float("nan")
    return {
        "run": label, "field": field, "pages": rows[["record_id", "page_number", "file_name"]].drop_duplicates().shape[0],
        "selected": len(selected), "true_selected": true_sel, "false_selected": false_sel,
        "false_in_edge_regions": int((edge & (selected["label"].astype(int) == 0)).sum()),
        "true_in_page": positives, "missed_true": positives - true_sel,
        "precision": round(precision, 4), "recall": round(recall, 4),
    }


def compare(reviewed: str, base: str, new: str) -> Path:
    base_frame, base_misses = _labelled(reviewed, base)
    new_frame, new_misses = _labelled(reviewed, new)
    fields = sorted(set(base_frame["field"]) | set(new_frame["field"]))
    table = []
    for field in fields:
        b = _field_row(base, field, base_frame, base_misses)
        n = _field_row(new, field, new_frame, new_misses)
        table.append({
            "field": field,
            "base_selected": b["selected"], "new_selected": n["selected"],
            "base_false": b["false_selected"], "new_false": n["false_selected"],
            "false_removed": b["false_selected"] - n["false_selected"],
            "base_true": b["true_selected"], "new_true": n["true_selected"],
            "true_lost": b["true_selected"] - n["true_selected"],
            "base_false_in_edge": b["false_in_edge_regions"], "new_false_in_edge": n["false_in_edge_regions"],
            "base_precision": b["precision"], "new_precision": n["precision"],
            "base_recall": b["recall"], "new_recall": n["recall"],
            "true_in_page": b["true_in_page"],
        })
    summary = pd.DataFrame(table)
    total = {column: summary[column].sum() for column in summary.columns if column not in {"field"} and not column.endswith(("precision", "recall"))}
    summary = pd.concat([summary, pd.DataFrame([{"field": "ALL", **total}])], ignore_index=True)

    # Candidates selected by one run and not the other (same candidate id).
    merged = base_frame[["candidate_id", "selected_now"]].merge(
        new_frame, on="candidate_id", how="outer", suffixes=("_base", ""), indicator=True
    )
    merged["selected_now_base"] = merged["selected_now_base"].fillna(False).astype(bool)
    merged["selected_now"] = merged["selected_now"].fillna(False).astype(bool)
    changed = merged[merged["selected_now_base"] != merged["selected_now"]].copy()
    changed["change"] = changed.apply(
        lambda row: ("dropped" if row["selected_now_base"] else "added")
        + (" TRUE" if row["label"] == 1 else " false"),
        axis=1,
    )
    keep = ["change", "record_id", "page_number", "file_name", "field", "region", "key", "value", "label",
            "band_header_bottom", "band_footer_top", "value_y0", "value_y1"]
    changes = changed[[column for column in keep if column in changed.columns]]

    out_dir = _run_dir(new)
    tag = _run_dir(base).name
    summary_path = out_dir / f"Compare_vs_{tag}.csv"
    summary.to_csv(summary_path, index=False)
    changes.to_csv(out_dir / f"Compare_vs_{tag}_changes.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(summary.to_string(index=False))
        print(f"\nchanged selections: {changes['change'].value_counts().to_dict() if len(changes) else 'none'}")
    print(f"\nwritten: {summary_path}")
    return summary_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reviewed", required=True, help="run holding the reviews (truth)")
    parser.add_argument("--base", required=True, help="unreviewed rerun with the baseline version")
    parser.add_argument("--new", required=True, help="unreviewed rerun with the experimental version")
    args = parser.parse_args()
    compare(args.reviewed, args.base, args.new)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
