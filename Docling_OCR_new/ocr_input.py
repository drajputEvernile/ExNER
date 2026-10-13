from __future__ import annotations

from typing import Any


def words_from_line(
    text: str, left: float, top: float, right: float, bottom: float
) -> list[dict[str, Any]]:
    """Split one OCR line into word boxes that share its height.

    Final1's reader (RapidOCR inside Docling, or RapidOCR-onnx) returns a box
    per line. The characters of each word take a share of that width, with one
    character of space between words. The polygon is the same four-corner shape
    Azure stores, top-left origin.
    """
    tokens = str(text or "").split()
    if not tokens or right <= left or bottom <= top:
        return []
    total = sum(len(token) for token in tokens) + max(len(tokens) - 1, 0)
    if total <= 0:
        return []
    span = right - left
    cursor = left
    words: list[dict[str, Any]] = []
    for index, token in enumerate(tokens):
        width = span * (len(token) / total)
        words.append({"content": token, "polygon": _polygon(cursor, top, cursor + width, bottom)})
        cursor += width
        if index < len(tokens) - 1:
            cursor += span / total
    return words


def _polygon(left: float, top: float, right: float, bottom: float) -> list[float]:
    return [
        round(left, 2), round(top, 2),
        round(right, 2), round(top, 2),
        round(right, 2), round(bottom, 2),
        round(left, 2), round(bottom, 2),
    ]

