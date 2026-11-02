"""Why is nothing extracted? Per record: images, OCR files, page matching, readable words, key-value hits.

    python check_input.py            # every record under Raw_Input
    python check_input.py REC_ID     # one record, with the first OCR word shown

Prints counts only (no page text) except with a record id, which shows the first OCR word's fields.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from Util import config
from Util.documents import _load_json, _match_pages, ocr_pages, raw_images, raw_records
from Util.geometry import words_from_page
from pipeline import extract_page_kv


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    print(f"Raw_Input : {config.Raw_Input}  exists={config.Raw_Input.is_dir()}")
    print(f"OCR_Input : {config.OCR_Input}  exists={config.OCR_Input.is_dir()}")
    ocr_dirs = {p.name.casefold(): p for p in config.OCR_Input.iterdir() if p.is_dir()}
    totals = dict(records=0, images=0, matched=0, with_words=0, with_values=0)
    for record, count in raw_records(config.Raw_Input):
        if only and record != only:
            continue
        totals["records"] += 1
        totals["images"] += count
        folder = ocr_dirs.get(record.casefold())
        if folder is None:
            print(f"{record}: images={count}  NO OCR FOLDER")
            continue
        jsons = sorted(folder.glob("*.json"))
        pages = ocr_pages(folder)
        images = raw_images(config.Raw_Input / record)
        matched, unmatched = _match_pages(pages, images)
        usable = [p for p in matched if words_from_page(p)]
        valued = 0
        for page in usable:
            result = extract_page_kv(page)
            valued += any(result.rows[name] for name in result.rows)
        totals["matched"] += len(matched)
        totals["with_words"] += len(usable)
        totals["with_values"] += valued
        print(f"{record}: images={count} json_files={len(jsons)} ocr_pages={len(pages)} matched={len(matched)} "
              f"readable_words={len(usable)} pages_with_a_candidate={valued} unmatched_ocr={len(unmatched)}")
        if only or (matched == [] and pages):
            print(f"   image names: {images[:3]}")
            print(f"   OCR fileNames: {[str(p.get('fileName')) for p in pages[:3]]}")
        if only and pages:
            data = _load_json(jsons[0]) or {}
            print(f"   json top-level keys: {list(data)[:8]}")
            page = pages[0]
            print(f"   page keys: {list(page)[:12]}")
            words = page.get("words") or []
            print(f"   words: {len(words)}; first word keys: {list(words[0]) if words and isinstance(words[0], dict) else words[:1]}")
            if words and isinstance(words[0], dict):
                print("   first word:", json.dumps(words[0])[:300])
    print("TOTAL", totals)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
