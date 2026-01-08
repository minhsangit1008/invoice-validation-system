# invoice-validation-system

POC for invoice validation (PDF -> OCR -> PO/DB match -> discrepancies).

## Quick start

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

Install Tesseract OCR (Windows example):
- https://github.com/UB-Mannheim/tesseract/wiki

## Data + OCR pipeline

```powershell
# 1) Download source PDFs
python .\scripts\download_sources.py

# 2) Download Vietnamese OCR data (optional)
python .\scripts\download_tessdata.py

# 3) Render PDFs + run OCR
python .\scripts\run_ocr.py

# 4) Build ground truth + OCR results + PO database
python .\scripts\build_ground_truth.py
python .\scripts\build_ocr_results.py
python .\scripts\build_database.py
```

## Data

Sample JSON files are in `data/`:

- `data/ground_truth.json`
- `data/ocr_results.json`
- `data/database.json`

OCR artifacts:
- `data/raw_pdfs/` (downloaded PDFs)
- `data/rendered_pages/` (PNG pages)
- `outputs/ocr_raw.json` (word/line OCR)

## Notebook

Open `data_overview.ipynb` in Jupyter/VS Code and Run All.

```powershell
python -m pip install notebook
jupyter notebook
```

## Option A (Logistic Regression)

```powershell
python .\scripts\train_model.py
```

Model will be saved to `models/logreg.pkl`.

## Demo + Sample Outputs

```powershell
python .\scripts\run_demo.py
python .\scripts\generate_sample_outputs.py
```

Outputs are saved under `sample_outputs/` and `sample_outputs/images/`.
