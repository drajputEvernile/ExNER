"""OCR pages by (RecordId, FileName), with words indexed the way the extractors index them."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from Util import config
from Util.documents import ocr_pages
from Util.geometry import Word, group_lines, page_size, words_from_page


@lru_cache(maxsize=8)
def _pages(folder: str, stamp: tuple) -> dict[str, dict[str, Any]]:
    del stamp
    return {str(page.get("fileName") or "").casefold(): page for page in ocr_pages(Path(folder))}


def load_page(record_id: str, file_name: str) -> dict[str, Any] | None:
    folder = Path(config.OCR_Input) / record_id
    if not folder.is_dir():
        return None
    stamp = tuple((path.name, path.stat().st_mtime) for path in sorted(folder.glob("*.json")))
    pages = _pages(str(folder), stamp)
    page = pages.get(file_name.casefold())
    if page is None:
        stem = Path(file_name).stem.casefold()
        same = [item for key, item in pages.items() if Path(key).stem == stem]
        page = same[0] if len(same) == 1 else None
    return page


def page_words(record_id: str, file_name: str) -> tuple[list[Word], float, float]:
    page = load_page(record_id, file_name)
    if page is None:
        return [], 1.0, 1.0
    words = words_from_page(page)
    page_w, page_h = page_size(page, words)
    return words, page_w, page_h


def page_lines(record_id: str, file_name: str) -> dict[str, Any]:
    """Words grouped into reading-order lines, boxes normalized to 0..1 of the page."""
    page = load_page(record_id, file_name)
    if page is None:
        return {"available": False, "lines": [], "text": ""}
    words = words_from_page(page)
    page_w, page_h = page_size(page, words)
    lines = [
        [
            {
                "i": word.index,
                "t": word.content,
                "b": [
                    round(word.box.left / page_w, 5),
                    round(word.box.top / page_h, 5),
                    round(word.box.right / page_w, 5),
                    round(word.box.bottom / page_h, 5),
                ],
            }
            for word in line
        ]
        for line in group_lines(words)
    ] if words else []
    text = str(page.get("content") or "").strip() or "\n".join(
        " ".join(word["t"] for word in line) for line in lines
    )
    return {"available": True, "lines": lines, "text": text}
