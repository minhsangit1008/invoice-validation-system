# invoice-validation-system

Proof-of-concept for an AI-powered invoice validation system.

## Setup

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
```

## Data

Sample JSON files are available in `data/`:

- `data/ground_truth.json`
- `data/ocr_results.json`
- `data/database.json`

The notebook also looks for these files in the repo root if needed.

## Notebook

Open `data_overview.ipynb` in Jupyter or VS Code and run the cells to generate
the data overview table.

If you want to run Jupyter locally:

```powershell
python -m pip install notebook
jupyter notebook
```

## Logistic Regression

Train a lightweight model on the sample data:

```powershell
python .\scripts\train_model.py
```

This writes `models/logreg.pkl`, which can be passed into `validate_invoice`
via the `model_bundle` argument (see `src/ml/train.py` and `src/ml/predict.py`).

## Demo and Sample Outputs

Run a demo over all invoices (prints to console):

```powershell
python .\scripts\run_demo.py
```

Generate sample output JSON files (validation + discrepancies + visualization):

```powershell
python .\scripts\generate_sample_outputs.py
```

Outputs are saved under `sample_outputs/`.

## Design Doc Export (DOCX)

```powershell
python .\scripts\export_design_docx.py
```
