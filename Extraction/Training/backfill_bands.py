"""Add the Heron band columns to the tables of runs made before they existed.

    python Training/backfill_bands.py KV_Run_A [KV_Run_B ...]

Runs the layout detector on each page image of the run (the images under config.Raw_Input) and
writes band_header_bottom, band_footer_top and band_outside into the key-value sheets' rows, next
to the reviews already there. Needed before training a version with --bands on those reviews.
Stop the Review UI first: both write the same CSV files. Nothing else in a row changes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from Heading.extract import BAND_DETECTOR, detect_all, load_detectors, page_image
from Training.features import SHEETS
from Util import config
from Util.bands import page_bands, outside_band
from Util.documents import load_documents
from Util.geometry import page_size, words_from_page

BAND_COLUMNS = ["band_header_bottom", "band_footer_top", "band_outside"]


def _run_dir(name: str) -> Path:
    path = Path(name)
    return path if path.is_dir() else config.Run_Output / name


def backfill(run: Path) -> None:
    tables = run / config.Tables_Folder
    frames = {name: pd.read_csv(tables / f"{name}.csv", dtype=str, keep_default_na=False) for name in SHEETS.values() if (tables / f"{name}.csv").is_file()}
    pages = sorted({
        (row["record_id"], row["file_name"], row["page_number"])
        for frame in frames.values() for row in frame[["record_id", "file_name", "page_number"]].to_dict("records")
    })
    documents, _, _ = load_documents(config.Raw_Input, config.OCR_Input)
    ocr_pages = {
        (doc.record_id, str(page.get("fileName") or ""), str(page.get("pageNumber") or "")): page
        for doc in documents for page in doc.pages
    }
    error = load_detectors().get(BAND_DETECTOR)
    if error:
        raise SystemExit(f"layout detector unavailable: {error}")
    bands: dict[tuple[str, str, str], tuple[str, str]] = {}
    for done, key in enumerate(pages, start=1):
        page, image = ocr_pages.get(key), None
        if page is not None:
            image = page_image(key[0], page)
        if page is None or image is None:
            bands[key] = ("", "")
            continue
        words = words_from_page(page)
        page_w, page_h = page_size(page, words)
        found = page_bands(detect_all(BAND_DETECTOR, image), image.size, words, page_w, page_h)
        bands[key] = ("" if found.header_bottom is None else str(found.header_bottom),
                      "" if found.footer_top is None else str(found.footer_top))
        if done % 25 == 0:
            print(f"{done}/{len(pages)} pages")
    for name, frame in frames.items():
        keys = list(zip(frame["record_id"], frame["file_name"], frame["page_number"]))
        frame["band_header_bottom"] = [bands.get(key, ("", ""))[0] for key in keys]
        frame["band_footer_top"] = [bands.get(key, ("", ""))[1] for key in keys]
        outside, _ = outside_band(frame.assign(field=name))
        frame["band_outside"] = ["" if pd.isna(value) else str(int(value)) for value in outside]
        frame.to_csv(tables / f"{name}.csv", index=False)
        print(f"{name}: {len(frame)} rows")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", help="run folders (names under config.Run_Output, or paths)")
    for name in parser.parse_args().runs:
        backfill(_run_dir(name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
