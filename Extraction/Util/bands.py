"""Per-page header and footer bands from the layout detector's page_header / page_footer boxes.

The fixed bands (Util/geometry.py HEADER_FRAC / FOOTER_FRAC) are the same on every page. A
Heron band follows the page: the header band runs from the top edge to the bottom of the
page_header boxes that connect to it, the footer band from the top of the page_footer boxes
that connect to the bottom edge to the bottom. Used only by experimental model versions
(manifest "bands": "filter" or "features"); a version without it ignores them.

Fractions are of the page height, 0 at the top. None = no band on that page (the fixed band
stays in force).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Detector whose page_header / page_footer boxes make the bands (Heading/extract.py DETECTORS).
BAND_DETECTOR = "heading_heron"

MIN_SCORE = 0.3          # lowest box score used
EDGE = 0.15              # the first box must start within this fraction of the page edge ...
GAP = 0.03               # ... and each next box within this fraction of the band so far
HEADER_CAP = 0.28        # the header band never reaches below this (the fixed band's edge)
FOOTER_CAP = 0.60        # the footer band never starts above this (looser than the fixed 0.80:
                         # a short page's footer line sits mid-page)


@dataclass(frozen=True)
class Bands:
    header_bottom: float | None = None
    footer_top: float | None = None


def _norm(box, size: tuple[int, int]) -> tuple[float, float, float, float]:
    width, height = size
    return box[0] / width, box[1] / height, box[2] / width, box[3] / height


def _header_bottom(boxes: list[tuple[float, float, float, float]]) -> float | None:
    reach: float | None = None
    for box in sorted(boxes, key=lambda item: item[1]):
        if box[1] <= (EDGE if reach is None else reach + GAP):
            reach = box[3] if reach is None else max(reach, box[3])
    return None if reach is None else round(min(reach, HEADER_CAP), 4)


def _footer_top(boxes: list[tuple[float, float, float, float]], word_centres: list[tuple[float, float]]) -> float | None:
    """Footer boxes connected to the bottom edge, or with no text below them but other footer boxes
    (a short page's last line is its footer wherever it sits)."""

    def in_footer(x: float, y: float) -> bool:
        return any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in boxes)

    def last_text(box: tuple[float, float, float, float]) -> bool:
        return all(in_footer(x, y) for x, y in word_centres if y > box[3])

    reach: float | None = None
    for box in sorted(boxes, key=lambda item: -item[3]):
        if reach is None:
            ok = 1.0 - box[3] <= EDGE or last_text(box)
        else:
            ok = box[3] >= reach - GAP
        if ok:
            reach = box[1] if reach is None else min(reach, box[1])
    return None if reach is None else round(max(reach, FOOTER_CAP), 4)


def page_bands(detections, image_size: tuple[int, int], words, page_w: float, page_h: float) -> Bands:
    """Bands of one page from every detection (any class) of the layout detector."""
    header = [_norm(d.box, image_size) for d in detections if d.det_class == "page_header" and d.score >= MIN_SCORE]
    footer = [_norm(d.box, image_size) for d in detections if d.det_class == "page_footer" and d.score >= MIN_SCORE]
    centres = [(word.box.cx / page_w, word.box.cy / page_h) for word in words] if page_w and page_h else []
    return Bands(_header_bottom(header), _footer_top(footer, centres))


def outside_band(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """(band_outside, band_dist) for candidate rows that carry the page's band_header_bottom /
    band_footer_top columns.

    A key-value candidate the fixed bands put in a header / footer region is outside when its
    box centre lies beyond the Heron band: band_outside 1, band_dist how far past the band edge
    (fraction of page height). Inside: 0 and a value <= 0. Blank (NaN) when the row is not in a
    header / footer region, is a heading, or its page has no band on that side."""
    def number(column: str) -> pd.Series:
        if column not in frame.columns:
            return pd.Series(float("nan"), index=frame.index)
        return pd.to_numeric(frame[column], errors="coerce")

    y_value = (number("value_y0") + number("value_y1")) / 2
    y_key = (number("key_y0") + number("key_y1")) / 2
    centre = y_value.fillna(y_key)
    region = frame["region"].astype(str).str.casefold() if "region" in frame.columns else pd.Series("", index=frame.index)
    heading = frame["field"].astype(str).isin(_HEADING_FIELDS) if "field" in frame.columns else pd.Series(False, index=frame.index)
    is_header = region.str.contains("header") & ~heading
    is_footer = region.str.contains("footer") & ~heading
    dist = pd.Series(float("nan"), index=frame.index)
    dist[is_header] = (centre - number("band_header_bottom"))[is_header]
    dist[is_footer] = (number("band_footer_top") - centre)[is_footer]
    outside = (dist > 0).astype(float).where(dist.notna())
    return outside, dist


# Heading sheets' field names (Heading/extract.py DETECTORS keys); duplicated to keep this module import-free.
_HEADING_FIELDS = frozenset({BAND_DETECTOR})
