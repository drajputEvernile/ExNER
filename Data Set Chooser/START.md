# Start the Data Set Chooser

Set the paths and `N` in `Data Set Chooser/config.py` first (absolute paths only):

| Setting | Meaning |
|---|---|
| `Raw_Read_Path` | folder of records to choose from: `{Raw_Read_Path}/{RecordId}/{page images}` |
| `Selected_Path` | one folder holding every selected page: `{Selected_Path}/{RecordId}__{page image}` |
| `N` | only records with N or fewer pages are listed (`0` = no limit) |

From the repo root (`E:\Projects\NER\NER`):

## One process (serves the built UI)

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --app-dir "Data Set Chooser" --host 127.0.0.1 --port 3002
```

Open http://127.0.0.1:3002.

## UI changes (dev server)

Run the backend as above, then:

```powershell
cd "Data Set Chooser\frontend"
npm install      # first time only
npm run dev      # http://127.0.0.1:3003
npm run build    # rebuild dist/ for the one-process mode
```

## Using it

Pick a record on the left, page through its images, and press **Select page for training**: that one
page image is copied into `Selected_Path` as `{RecordId}__{page file name}`. A selected page shows
**Selected · Remove** and a ✓ in the filmstrip; Remove deletes only that copy (never the raw image).
Selection is read from the folder itself, so restarting loses nothing.
