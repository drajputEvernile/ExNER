"""Download every model Docling_OCR_new needs, into this folder only.

    python download_models.py

RapidOCR torch weights -> models/rapidocr   (ModelScope, RapidAI v3.9.2)
Docling layout + table -> models/docling    (HuggingFace, cached under models/hf_cache)
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import config  # noqa: E402

os.environ.setdefault("HF_HOME", config.HF_HOME)

BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2"
RAPID_FILES = {
    "PP-OCRv6_det_small.pth": f"{BASE}/torch/PP-OCRv6/det/PP-OCRv6_det_small.pth",
    "PP-OCRv6_rec_small.pth": f"{BASE}/torch/PP-OCRv6/rec/PP-OCRv6_rec_small.pth",
    "ch_ptocr_mobile_v2.0_cls_mobile.pth": f"{BASE}/torch/PP-OCRv4/cls/ch_ptocr_mobile_v2.0_cls_mobile.pth",
    "ppocrv6_dict.txt": f"{BASE}/paddle/PP-OCRv6/rec/PP-OCRv6_rec_small/ppocrv6_dict.txt",
}


def download_rapidocr() -> None:
    dest = Path(config.RAPID_MODELS_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    for name, url in RAPID_FILES.items():
        target = dest / name
        if target.is_file() and target.stat().st_size > 0:
            print(f"have  {name}")
            continue
        print(f"fetch {name}")
        urllib.request.urlretrieve(url, target)
        print(f"      {target.stat().st_size / 1e6:.1f} MB")


def download_docling() -> None:
    from docling.utils.model_downloader import download_models

    dest = Path(config.DOCLING_ARTIFACTS_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    download_models(
        output_dir=dest,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=False,
        with_picture_classifier=False,
        with_rapidocr=False,
    )
    print("docling layout + tableformer ->", dest)


if __name__ == "__main__":
    download_rapidocr()
    download_docling()
