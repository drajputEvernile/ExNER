# ExNER: key/value extraction from chart pages

Run every command from the repo root (`E:\Projects\ExNER`) with the repo `.venv`.

## Setup (once)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd Extraction\Review_UI\frontend; npm install; cd ..\..\..
cd "Data Set Chooser\frontend"; npm install; cd ..\..
```

## Data layout (`Data\`)

| Folder | Content |
|---|---|
| `RAW\` | original page images (HEIC, JPG, PNG ...), one file per record |
| `Pages\` | upright JPEG copy of each RAW image, `{record}\{record}.jpg` (made by the OCR step) |
| `OCR\` | OCR JSON, `{record}\{record}.json` (made by the OCR step) |
| `Extraction\` | extraction output: `Runs\KV_Run_{timestamp}\KV_Extraction\*.csv`, training data, logs |
| `Training_Set\` | pages picked with the Data Set Chooser |

All paths are set in `Extraction\Util\config.py`, `Docling_OCR_new\config.py` and `Data Set Chooser\config.py`.

## a. Run the extraction module

Needs the OCR step (b) first. Reads `Data\OCR` and `Data\Pages`, writes to `Data\Extraction`.

```powershell
.\.venv\Scripts\python.exe Extraction\run.py --fresh
```

Resume a stopped run: `.\.venv\Scripts\python.exe Extraction\run.py`
Rules only (no trained models): add `--model-version v0`.

## b. Run the Docling OCR

Reads every image in `Data\RAW`, writes `Data\Pages` and `Data\OCR`. Images already done are skipped.

```powershell
.\.venv\Scripts\python.exe Docling_OCR_new\run.py
.\.venv\Scripts\python.exe Docling_OCR_new\run.py --limit 3     # quick test on the first 3
```

## c. Start the review UI

Backend (terminal 1):

```powershell
.\.venv\Scripts\python.exe -m uvicorn Review_UI.backend.app:app --app-dir Extraction --host 127.0.0.1 --port 3000 --reload
```

Frontend (terminal 2):

```powershell
cd Extraction\Review_UI\frontend
npm run dev
```

Open http://127.0.0.1:3001.

## d. Start the data chooser

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --app-dir "Data Set Chooser" --host 127.0.0.1 --port 3002
```

Open http://127.0.0.1:3002 (serves the built UI; for UI development run `npm run dev` in `Data Set Chooser\frontend`, http://127.0.0.1:3003).
