# Design Document - Invoice Validation System

## Overview
This document describes a proof-of-concept invoice validation system that
uses real PDF invoices from the internet, runs OCR to extract fields, compares
them against ground truth and PO/database records, highlights discrepancies,
and outputs validation status with confidence.

## Approach
1. Data ingestion + OCR
   - `data/sources.csv` drives downloads into `data/raw_pdfs/`.
   - Render PDFs to PNG at 300 DPI with optional scan simulation.
   - Run Tesseract OCR (eng+vie) to get word boxes, line text, and confidence.
   - Save raw OCR to `outputs/ocr_raw.json`.

2. Ground truth + database
   - Parse the PDF text layer to build `data/ground_truth.json` (header fields
     + basic line items where possible).
   - Clean noisy name/address candidates and skip obviously invalid labels.
   - Build `data/database.json` (PO + vendor_master + customer_info), and inject
     negative cases for ~30% invoices to show business-rule discrepancies.

3. Normalization
   - Text: lowercase, strip punctuation, collapse whitespace.
   - Company suffix normalization (inc, llc, ltd, co).
   - Address abbreviation normalization (street -> st, drive -> dr).
   - OCR confusable mapping (O/0, I/1/l, S/5, B/8).

4. Matching and validation
   - ID fields (PO): exact match after OCR-confusion normalization.
   - Names/addresses: fuzzy similarity (token set + edit ratio).
   - Dates: tolerance window in days.
   - Amounts: absolute and relative tolerance.
   - Database references:
     - PO vendor used as primary expected vendor name.
     - vendor_master address used for vendor address validation when available.
     - customer_info billing_address used for customer address validation.
     - tax_rate from PO used to cross-check tax_amount.
   - Line items: parse text to (description, qty, unit_price, total).
     - Item not in PO list -> critical.
     - Quantity above max -> critical.
     - Line total mismatch -> warning.

5. Discrepancy scoring and status
   - Discrepancy severity: critical / warning / informational.
   - Overall confidence combines OCR confidence and rule penalties.
   - Status logic:
     - critical -> rejected.
     - warnings or low confidence -> needs_review.
     - otherwise approved.

6. Option A (ML)
   - Logistic regression predicts probability a field is wrong.
   - Features: OCR confidence, text length, digit ratio, fuzzy score,
     amount/date diffs, field identity.
   - Model output calibrates confidence per field and overall score.

7. Output generation
   - `scripts/generate_sample_outputs.py` writes JSON results per invoice.
   - `src/output/visualize.py` draws highlighted PNGs from discrepancy boxes.

## Sample Outputs (Images)
These are example highlighted outputs showing discrepancy boxes.
![INV-G-001 header highlights](sample_outputs/images/INV-G-001_p1.png)
![INV-G-003 header + line item highlights](sample_outputs/images/INV-G-003_p1.png)
![INV-G-010 header highlights](sample_outputs/images/INV-G-010_p1.png)

## Ground Truth vs PO Comparison (Example)
Ground truth comes from `data/ground_truth.json` and PO data comes from
`data/database.json`. The validator compares OCR results against ground truth
and then cross-checks against PO constraints (vendor, tax_rate, approved_amount).

Ground truth entry (invoice_id = INV-G-010):
```json
{
  "invoice_id": "INV-G-010",
  "source_pdf": "data/raw_pdfs/INV-G-010.pdf",
  "expected_data": {
    "vendor_name": null,
    "vendor_address": null,
    "customer_name": "Test Business",
    "customer_address": "123 Somewhere St, Melbourne, VIC 3000",
    "po_number": "12345",
    "invoice_date": "2016-01-25",
    "due_date": "2016-01-31",
    "subtotal": 85.0,
    "tax_amount": 8.5,
    "total_amount": 93.5,
    "line_items": []
  }
}
```

PO record used for comparison (po_number = 12345):
```json
{
  "po_number": "12345",
  "vendor": null,
  "approved_amount": 93.5,
  "valid_items": [],
  "max_quantity": {},
  "tax_rate": 0.1
}
```

## Pipeline Diagram
```mermaid
flowchart LR
    SRC[data/sources.csv] --> PDF[raw_pdfs/*.pdf]
    PDF --> R[Render to PNG]
    R --> OCR[OCR (Tesseract)]
    OCR --> RAW[ocr_raw.json]
    RAW --> PARSE[Field extraction]
    PARSE --> OCRRES[ocr_results.json]
    GT[ground_truth.json] --> V[Validation Rules]
    DB[database.json] --> V
    OCRRES --> N[Normalization]
    N --> V
    V --> D[Discrepancies]
    V --> L[Line Item Parsing/Anomaly]
    L --> D
    D --> C[Confidence Scoring]
    C --> S[Status Decision]
    D --> VIZ[Visualization Coords]
    V --> ML[Option A: Logistic Regression]
    ML --> C
    S --> OUT[Output JSON]
    VIZ --> OUT
    VIZ --> IMG[Highlighted Images]
```

## Rule Rationale & Thresholds
- PO/ID fields: strict matching is required because they drive payment linkage
  and vendor approval; OCR-confusion normalization (O/0, I/1/l, S/5, B/8)
  reduces false rejections from common OCR errors.
- Names/addresses: fuzzy matching handles abbreviations and truncation; thresholds
  are softer to avoid penalizing minor formatting differences.
- Dates: tolerance of 1-3 days is treated as warning based on typical OCR/entry
  drift; larger gaps are critical.
- Amounts: combined absolute and relative tolerance captures rounding/tax noise
  across both small and large invoices.
- Tax: tax_amount is cross-checked against PO tax_rate when available to validate
  accounting consistency.
- Line items: items not in PO list or quantity above max are critical because
  they violate approved purchasing rules; line total drift is warning to allow
  minor rounding.
- Status policy: critical issues are rejected; warnings or low confidence stay
  in needs_review for human inspection.

## Assumptions and Limitations
- OCR quality varies by template; some PDFs are closer to forms than real scans.
- Ground truth uses heuristic extraction + cleanup and may miss uncommon layouts.
- Limited sample size: ML model is illustrative only.
- Address parsing is token-based, not full geocoding.

## Scalability Considerations
- Batch or streaming validation supported (stateless rules).
- Thresholds and mappings are centralized in config for tuning.
- Add vendor-specific templates to improve field extraction.
- Introduce async processing for large volumes.

## Deliverables Mapping
- Notebook: data overview and metrics (`data_overview.ipynb`).
- Core engine: `src/*` modules.
- Sample outputs: `sample_outputs/*.json` + `sample_outputs/images/*.png`.
- Tests: pytest with 15 cases.
