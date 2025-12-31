# invoice-validation-system

POC for invoice validation (OCR -> PO/DB match -> discrepancies).

## Quick start

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## Data

Sample JSON files are in `data/`:

- `data/ground_truth.json`
- `data/ocr_results.json`
- `data/database.json`

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

Outputs are saved under `sample_outputs/`.

## Design Document

- `Design Document.docx`
- `DESIGN.md`
