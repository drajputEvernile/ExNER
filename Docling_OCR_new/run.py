"""Run Docling + RapidOCR on the page images in Data/RAW and write the OCR JSON Extraction reads.

    python run.py                 # every image in Data/RAW (HEIC, JPG, PNG, ...)
    python run.py --limit 3       # only the first 3 (quick check)
    python run.py path\\to\\img.heic  # one image

Each image is one record. HEIC/other images are saved as a JPEG page image
(Data/Pages/<record>/<record>.jpg, EXIF-rotated) and the OCR is written to
Data/OCR/<record>/<record>.json as {"pages": [{fileName, pageNumber, width, height,
content, words, section_headers}]}. Images that already have an OCR JSON are skipped.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import config  # noqa: E402

# Hub downloads (layout / table models) stay inside this folder.
os.environ.setdefault("HF_HOME", config.HF_HOME)

import docling_ocr  # noqa: E402

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".heic", ".heif"}


def pick_images(args: argparse.Namespace) -> list[Path]:
    if args.paths:
        return [Path(p) for p in args.paths]
    images = sorted(
        (f for f in Path(config.DATA_RAW_DIR).rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda f: f.name.casefold(),
    )
    return images[: args.limit] if args.limit else images


def save_page_image(image: Path, record: str) -> Path:
    """JPEG copy of the image (upright, RGB) under Data/Pages/<record>/."""
    from PIL import Image, ImageOps

    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    page = Path(config.PAGES_DIR) / record / f"{record}.jpg"
    page.parent.mkdir(parents=True, exist_ok=True)
    if not page.is_file():
        ImageOps.exif_transpose(Image.open(image)).convert("RGB").save(page, quality=95)
    return page


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    status = docling_ocr.docling_status()
    print("status:", status)
    converter = docling_ocr.get_converter()
    if converter is None:
        sys.exit(f"Docling unavailable: {docling_ocr.converter_reason()}")

    for image in pick_images(args):
        record = image.stem
        out_file = Path(config.OUTPUT_DIR) / record / f"{record}.json"
        if out_file.is_file():
            print(f"{record}: already done")
            continue
        page_image = save_page_image(image, record)
        result = docling_ocr.convert_image(page_image, converter)
        result.pop("document", None)
        page = {"fileName": page_image.name, "pageNumber": 1, **result}
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps({"pages": [page]}, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{record}: {len(result['words'])} words, {len(result['section_headers'])} headers, "
              f"{result['elapsed_seconds']:.1f}s")


if __name__ == "__main__":
    main()
