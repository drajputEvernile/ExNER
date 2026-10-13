"""Train the heading ranker on this machine from a reviewed run. No page images are read.

The reviews already in that run's Headings sheet are the training set. Do not copy them anywhere.

    .\\.venv\\Scripts\\python.exe Extraction\\Training\\train_headings.py KV_Run_<the reviewed run>

About 1 record in 5 is held out, and the printed counts are on those records only.
The ranker is written beside the KV model when that heading folder is still empty, so a run
with --model-version v004 keeps KV_v004 and starts using the new heading ranker.
If that heading folder already exists, the next free number is used and the run needs
--heading-version.

Heading_v003 is a 3-page experiment. Do not run it. Copy back only the new Heading_vNNN folder.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from Training import registry
from Training.dataset import write
from Training.train import train
from Util import config


def _reviewed_pages(run_name: str) -> int:
    folder = Path(run_name) if Path(run_name).is_absolute() else Path(config.Run_Output) / run_name
    sheet = folder / config.Tables_Folder / "Headings.csv"
    if not sheet.is_file():
        raise SystemExit(f"No Headings sheet at {sheet}. Pass the run folder that was reviewed on this machine.")
    frame = pd.read_csv(sheet, dtype=str, keep_default_na=False, usecols=lambda name: name in {"reviewed_at", "record_id", "page_number", "file_name"})
    reviewed = frame[frame["reviewed_at"].astype(str).str.strip() != ""]
    if reviewed.empty:
        raise SystemExit(f"{sheet} has no reviewed rows (reviewed_at is empty).")
    pages = reviewed[["record_id", "page_number", "file_name"]].drop_duplicates()
    return len(pages)


def _print_counts(metrics: dict) -> None:
    fields = (metrics.get("test") or {}).get("fields") or {}
    entry = fields.get("heading_heron") or {}
    print("\nHeld-out records (the ranker did not train on these)")
    print(f"{'':22s} {'accuracy':>9s} {'correct':>8s} {'incorrect':>10s} {'missed':>7s}")
    for name, block in (("rules", entry.get("v0") or {}), ("ranker", entry.get("model") or {})):
        if not block:
            continue
        print(
            f"{name:22s} {str(block.get('accuracy')):>8s}% {block.get('right', 0):8d} "
            f"{block.get('wrong', 0):10d} {block.get('missed', 0):7d}"
        )
        print(
            f"{'':22s} precision {block.get('precision')}  recall {block.get('recall')}  "
            f"level {block.get('level_accuracy')}  "
            f"false headings {block.get('fp')}  missed headings {block.get('fn')}"
        )
    print("Correct means the text and the level are both right. Incorrect includes a false heading and a wrong level.")


def main() -> int:
    runs = sys.argv[1:]
    if not runs or runs[0].startswith("-"):
        raise SystemExit(__doc__.strip().splitlines()[0] + "\n\n" + __doc__.split("\n\n")[1])
    pages = sum(_reviewed_pages(name) for name in runs)
    print(f"Reviewed heading pages: {pages} across {len(runs)} run(s).")
    if pages < 30:
        raise SystemExit("Fewer than 30 reviewed heading pages. The ranker needs more reviews than that.")

    dataset = write(runs)
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    heading = (manifest.get("fields") or {}).get("heading_heron") or {}
    print(
        f"Dataset {dataset.name}: {heading.get('groups', 0)} heading pages, "
        f"{heading.get('positives', 0)} true candidates, {heading.get('generator_misses', 0)} headings no candidate proposed."
    )

    target = config.Default_Model_Version
    version = registry.next_version("heading")
    paired = version == target
    print(f"Writing Heading_{version}" + (f" beside KV_{target}." if paired else ". The KV model keeps its own number."))
    folders = train(
        str(dataset),
        30,
        f"Heading ranker on {', '.join(runs)}. Hold-out is about 1 record in 5. Not Heading_v003.",
        "train",
        ("heading",),
        None,
        version,
    )
    if not folders:
        raise SystemExit("Nothing was saved.")
    metrics = json.loads((folders[0] / "metrics.json").read_text(encoding="utf-8"))
    _print_counts(metrics)
    print(f"\nSaved {folders[0]}")
    if paired:
        print(f"A run with --model-version {target} now uses KV_{target} and this heading ranker.")
    else:
        print(f"Run with --model-version {config.Default_Model_Version} --heading-version {version}")
    print("Copy this Heading folder back. Leave the review sheets on this machine.")
    print("Do not run Heading_v003. It was trained on 1 record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
