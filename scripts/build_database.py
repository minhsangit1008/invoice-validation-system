import json
import math
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.preprocess.normalize import parse_amount


def _compute_tax_rate(subtotal, tax_amount):
    sub = parse_amount(subtotal)
    tax = parse_amount(tax_amount)
    if sub is None or tax is None or sub == 0:
        return None
    return round(tax / sub, 4)


def build_database(ground_truth, negative_ratio=0.3):
    purchase_orders = {}
    vendor_master = {}
    customer_info = {}

    invoices = ground_truth.get("invoices", [])
    total = len(invoices)
    negative_count = max(1, math.floor(total * negative_ratio)) if total else 0
    negative_ids = {inv["invoice_id"] for inv in invoices[:: max(1, total // max(1, negative_count))]}

    for inv in invoices:
        inv_id = inv.get("invoice_id")
        exp = inv.get("expected_data", {})
        vendor_name = exp.get("vendor_name")
        vendor_address = exp.get("vendor_address")
        customer_name = exp.get("customer_name")
        customer_address = exp.get("customer_address")

        if vendor_name and vendor_name not in vendor_master:
            vendor_master[vendor_name] = {
                "legal_name": vendor_name,
                "address": vendor_address,
                "tax_id": None,
            }
        if customer_name and customer_name not in customer_info:
            customer_info[customer_name] = {
                "legal_name": customer_name,
                "billing_address": customer_address,
            }

        po_number = exp.get("po_number")
        if not po_number:
            continue

        line_items = exp.get("line_items") or []
        valid_items = [li.get("description") for li in line_items if li.get("description")]
        max_quantity = {
            li.get("description"): li.get("quantity")
            for li in line_items
            if li.get("description") and li.get("quantity") is not None
        }

        subtotal = exp.get("subtotal")
        tax_amount = exp.get("tax_amount")
        total_amount = exp.get("total_amount")
        approved_amount = parse_amount(total_amount) or parse_amount(subtotal) or 0.0
        tax_rate = _compute_tax_rate(subtotal, tax_amount)

        po_record = {
            "vendor": vendor_name,
            "approved_amount": approved_amount,
            "valid_items": valid_items,
            "max_quantity": max_quantity,
            "tax_rate": tax_rate,
        }

        if inv_id in negative_ids:
            if po_record["approved_amount"]:
                po_record["approved_amount"] = round(po_record["approved_amount"] * 0.9, 2)
            if po_record["valid_items"]:
                po_record["valid_items"] = po_record["valid_items"][:-1]
            if po_record["max_quantity"]:
                for key in list(po_record["max_quantity"].keys())[:1]:
                    po_record["max_quantity"][key] = max(1, po_record["max_quantity"][key] - 1)

        purchase_orders[po_number] = po_record

    return {
        "purchase_orders": purchase_orders,
        "vendor_master": vendor_master,
        "customer_info": customer_info,
    }


def main():
    ground_truth_path = ROOT_DIR / "data" / "ground_truth.json"
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    database = build_database(ground_truth)
    out_path = ROOT_DIR / "data" / "database.json"
    out_path.write_text(json.dumps(database, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {out_path}")


if __name__ == "__main__":
    main()
