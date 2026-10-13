"""Local API for the Data Set Chooser.

Records are the folders under config.Raw_Read_Path; each holds one image per page. Selecting a
page copies that one image into the single folder config.Selected_Path as
{RecordId}__{page file name}. A page counts as selected when that file is present, so the
destination folder is the only state: nothing else is stored.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config

SEP = "__"  # Selected_Path file name = {RecordId}{SEP}{page file name}
SUPPORTED = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}

app = FastAPI(title="Data Set Chooser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _natural(name: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", name)]


def _pages(record_dir: Path) -> list[Path]:
    try:
        files = [path for path in record_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED]
    except OSError:
        return []
    return sorted(files, key=lambda path: _natural(path.name))


def _record_dirs() -> list[Path]:
    root = Path(config.Raw_Read_Path)
    if not root.is_dir():
        return []
    return sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: _natural(path.name))


def _resolve_record(record_id: str) -> tuple[Path, list[Path]]:
    if not record_id or "/" in record_id or "\\" in record_id or record_id in {".", ".."}:
        raise HTTPException(404, "record not found")
    record_dir = Path(config.Raw_Read_Path) / record_id
    pages = _pages(record_dir) if record_dir.is_dir() else []
    if not pages:
        raise HTTPException(404, "record not found")
    return record_dir, pages


def _copy_name(record_id: str, file_name: str) -> str:
    return f"{record_id}{SEP}{file_name}"


def _copy_path(record_id: str, file_name: str) -> Path:
    return Path(config.Selected_Path) / _copy_name(record_id, file_name)


def _selected_pages(record_id: str, pages: list[Path]) -> list[str]:
    return [page.name for page in pages if _copy_path(record_id, page.name).is_file()]


def _limit_ok(page_count: int) -> bool:
    return config.N == 0 or page_count <= config.N


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/records")
def list_records() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    hidden = 0
    for record_dir in _record_dirs():
        pages = _pages(record_dir)
        if not pages:
            continue
        if not _limit_ok(len(pages)):
            hidden += 1
            continue
        records.append(
            {
                "record_id": record_dir.name,
                "page_count": len(pages),
                "pages": [page.name for page in pages],
                "selected_pages": _selected_pages(record_dir.name, pages),
            }
        )
    return {
        "raw_path": str(config.Raw_Read_Path),
        "selected_path": str(config.Selected_Path),
        "n": config.N,
        "records": records,
        "shown": len(records),
        "selected": sum(len(record["selected_pages"]) for record in records),
        "hidden_over_n": hidden,
    }


@app.get("/api/image")
def get_image(record_id: str, file_name: str) -> FileResponse:
    _, pages = _resolve_record(record_id)
    for page in pages:
        if page.name == file_name:
            return FileResponse(page)
    raise HTTPException(404, f"image not found for {record_id}/{file_name}")


def _resolve_page(record_id: str, file_name: str) -> Path:
    _, pages = _resolve_record(record_id)
    for page in pages:
        if page.name == file_name:
            if not _limit_ok(len(pages)):
                raise HTTPException(409, f"{record_id} has {len(pages)} pages, more than N={config.N}")
            return page
    raise HTTPException(404, f"image not found for {record_id}/{file_name}")


@app.post("/api/pages/select")
def select_page(record_id: str, file_name: str) -> dict[str, Any]:
    """Copy one page image into Selected_Path as {record_id}__{file_name}. Safe to repeat."""
    page = _resolve_page(record_id, file_name)
    destination = _copy_path(record_id, file_name)
    try:
        Path(config.Selected_Path).mkdir(parents=True, exist_ok=True)
        if not destination.is_file():
            partial = destination.with_name(destination.name + ".part")
            shutil.copy2(page, partial)
            os.replace(partial, destination)
    except OSError as exc:
        raise HTTPException(500, f"Could not copy {record_id}/{file_name}: {exc}") from exc
    return {"record_id": record_id, "file_name": file_name, "selected": True, "copied_to": str(destination)}


@app.delete("/api/pages/select")
def unselect_page(record_id: str, file_name: str) -> dict[str, Any]:
    """Remove the copy made by select. Only a file the same size as its raw image is deleted."""
    page = _resolve_page(record_id, file_name)
    copy = _copy_path(record_id, file_name)
    try:
        if copy.is_file() and copy.stat().st_size == page.stat().st_size:
            copy.unlink()
    except OSError as exc:
        raise HTTPException(500, f"Could not remove {record_id}/{file_name}: {exc}") from exc
    return {"record_id": record_id, "file_name": file_name, "selected": copy.is_file()}


_dist = ROOT / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
