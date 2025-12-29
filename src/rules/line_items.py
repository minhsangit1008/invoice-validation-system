import re

from src.output.notifications import build_discrepancy
from src.preprocess.normalize import parse_amount, safe_int


_QTY_RE = re.compile(r"qty\s*[:=]?\s*(\d+)", re.IGNORECASE)
_PRICE_RE = re.compile(r"price\s*[:=]?\s*\$?([0-9,\.]+)", re.IGNORECASE)
_TOTAL_RE = re.compile(r"total\s*[:=]?\s*\$?([0-9,\.]+)", re.IGNORECASE)


def parse_line_item_text(text):
    if not text:
        return {}
    desc = text.split("\n")[0].strip()
    qty = _match_number(_QTY_RE, text, int_only=True)
    price = _match_number(_PRICE_RE, text)
    total = _match_number(_TOTAL_RE, text)
    return {
        "description": desc,
        "quantity": qty,
        "unit_price": price,
        "total": total,
    }


def _match_number(pattern, text, int_only=False):
    m = pattern.search(text)
    if not m:
        return None
    val = m.group(1)
    if int_only:
        return safe_int(val)
    return parse_amount(val)


def validate_line_items(ocr_items, expected_items, po_record, bbox_map=None):
    discrepancies = []
    bbox_map = bbox_map or {}

    parsed_items = []
    for item in ocr_items or []:
        if isinstance(item, dict) and "text" in item:
            parsed_items.append(parse_line_item_text(item.get("text")))
        else:
            parsed_items.append(item)

    valid_items = set(po_record.get("valid_items", [])) if po_record else set()
    max_quantity = po_record.get("max_quantity", {}) if po_record else {}

    for idx, item in enumerate(parsed_items):
        desc = (item or {}).get("description")
        qty = (item or {}).get("quantity")
        unit_price = (item or {}).get("unit_price")
        total = (item or {}).get("total")

        field_prefix = f"line_items[{idx}]"

        if desc and valid_items and desc not in valid_items:
            discrepancies.append(
                build_discrepancy(
                    f"{field_prefix}.description",
                    "critical",
                    "item_in_po",
                    desc,
                    0.9,
                    "Item not in approved PO list",
                    bbox_map.get("line_items"),
                )
            )

        if desc and desc in max_quantity and qty is not None:
            max_qty = max_quantity.get(desc)
            if max_qty is not None and qty > max_qty:
                discrepancies.append(
                    build_discrepancy(
                        f"{field_prefix}.quantity",
                        "critical",
                        max_qty,
                        qty,
                        0.9,
                        "Quantity exceeds PO limit",
                        bbox_map.get("line_items"),
                    )
                )

        if qty is not None and unit_price is not None and total is not None:
            expected_total = qty * unit_price
            diff = abs(expected_total - total)
            if diff > 1.0:
                discrepancies.append(
                    build_discrepancy(
                        f"{field_prefix}.total",
                        "warning",
                        round(expected_total, 2),
                        total,
                        0.7,
                        "Line total mismatch",
                        bbox_map.get("line_items"),
                    )
                )

    return discrepancies, parsed_items
