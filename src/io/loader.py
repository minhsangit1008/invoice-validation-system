import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_all(data_dir):
    data_dir = Path(data_dir)
    ground_truth = load_json(data_dir / "ground_truth.json")
    ocr_results = load_json(data_dir / "ocr_results.json")
    database = load_json(data_dir / "database.json")
    _validate_min_schema(ground_truth, ocr_results, database)
    return ground_truth, ocr_results, database


def _validate_min_schema(ground_truth, ocr_results, database):
    if "invoices" not in ground_truth:
        raise ValueError("ground_truth.json missing 'invoices'")
    if not isinstance(ocr_results, dict):
        raise ValueError("ocr_results.json must be a dict keyed by invoice_id")
    for key in ("purchase_orders", "vendor_master", "customer_info"):
        if key not in database:
            raise ValueError(f"database.json missing '{key}'")


def ground_truth_map(ground_truth):
    mapping = {}
    for inv in ground_truth.get("invoices", []):
        inv_id = inv.get("invoice_id")
        if inv_id:
            mapping[inv_id] = inv
    return mapping
