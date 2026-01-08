import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import RAW_PDF_DIR, SIMULATE_SCAN_IDS
from src.preprocess.normalize import collapse_whitespace, normalize_text, parse_amount, parse_date


_DATE_LABELS = [
    "invoice date",
    "inv date",
    "date",
]
_DUE_LABELS = [
    "due date",
    "payment due",
    "due",
]
_PO_LABELS = [
    "po number",
    "po#",
    "po",
    "p.o.",
    "purchase order",
    "order number",
]
_SUBTOTAL_LABELS = ["subtotal", "sub total"]
_TAX_LABELS = ["tax", "vat"]
_TOTAL_LABELS = ["total due", "amount due", "balance due"]

_STOP_WORDS = [
    "bill to",
    "billed to",
    "ship to",
    "sold to",
    "to:",
    "from:",
    "date",
    "due",
    "total",
    "subtotal",
    "tax",
    "amount",
    "po",
    "order",
]

_COMPANY_RE = re.compile(r"\b(inc|llc|ltd|co|company|corp|corporation)\b", re.IGNORECASE)


def _clean_lines(text):
    lines = []
    for raw in text.splitlines():
        line = collapse_whitespace(raw)
        if line:
            lines.append(line)
    return lines


def _find_by_labels(lines, labels):
    for line in lines:
        norm = normalize_text(line)
        for label in labels:
            if label in norm:
                return line
    return None


def _extract_after_label(line, labels):
    norm = normalize_text(line)
    for label in labels:
        if label in norm:
            idx = norm.find(label) + len(label)
            raw = line[idx:].strip(" :\t-")
            return raw or None
    return None


def _extract_amount(lines, labels, exclude_terms=None):
    exclude_terms = exclude_terms or []
    for line in lines:
        norm = normalize_text(line)
        if any(label in norm for label in labels) and not any(
            term in norm for term in exclude_terms
        ):
            amt = _last_amount_in_line(line)
            if amt is not None:
                return amt
    return None


def _last_amount_in_line(line):
    candidates = re.findall(r"[$€£]?\s*[\d,.\(\)-]+", line)
    for raw in reversed(candidates):
        val = parse_amount(raw)
        if val is not None:
            return val
    return None


def _normalize_date_text(raw):
    if not raw:
        return raw
    return re.sub(r"(\d{2})\s+(\d{2})\b", r"\1\2", raw)


def _extract_date(lines, labels, exclude_terms=None):
    exclude_terms = exclude_terms or []
    for line in lines:
        norm = normalize_text(line)
        if any(label in norm for label in labels) and not any(
            term in norm for term in exclude_terms
        ):
            raw = _extract_after_label(line, labels)
            if raw:
                parsed = parse_date(_normalize_date_text(raw))
                if parsed and 1900 <= parsed.year <= 2100:
                    return parsed.isoformat()
                return None
    return None


def _extract_block(lines, start_keywords):
    for idx, line in enumerate(lines):
        norm = normalize_text(line)
        if any(_starts_with_label(norm, keyword) for keyword in start_keywords):
            block = []
            for nxt in lines[idx + 1 :]:
                nxt_norm = normalize_text(nxt)
                if any(_starts_with_label(nxt_norm, stop) for stop in _STOP_WORDS):
                    break
                block.append(nxt)
            return block
    return []


def _starts_with_label(norm, label):
    return re.match(rf"^{re.escape(label)}(\b|\s|:)", norm) is not None


def _extract_party(lines, start_keywords, inline_labels=None, fallback_start=0):
    inline_labels = inline_labels or []
    for idx, line in enumerate(lines):
        inline = _extract_inline_value(line, inline_labels)
        if inline:
            if not _is_name_candidate(inline):
                break
            address_lines = _collect_address(lines[idx + 1 :])
            address = ", ".join(address_lines[:2]) if address_lines else None
            return inline, address

    block = _extract_block(lines, start_keywords)
    if block:
        name = _pick_name(block)
        address_lines = [line for line in block if line != name]
        address = ", ".join(address_lines[:2]) if address_lines else None
        return name or None, address or None

    company = _find_company_line(lines)
    if company:
        return company, None

    fallback = lines[fallback_start : fallback_start + 4]
    if not fallback:
        return None, None
    name = _pick_name(fallback)
    address_lines = [line for line in fallback if line != name]
    address = ", ".join(address_lines[:2]) if address_lines else None
    return name or None, address or None


def _extract_inline_value(line, labels):
    for label in labels:
        m = re.match(rf"{re.escape(label)}\s*:?\s*(.+)$", line, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _collect_address(lines):
    collected = []
    for nxt in lines:
        nxt_norm = normalize_text(nxt)
        if any(_starts_with_label(nxt_norm, stop) for stop in _STOP_WORDS):
            break
        collected.append(nxt)
    return collected


def _find_company_line(lines):
    for line in reversed(lines):
        if _COMPANY_RE.search(line) and _is_name_candidate(line):
            return line
    return None


def _is_name_candidate(line):
    letters = sum(ch.isalpha() for ch in line)
    digits = sum(ch.isdigit() for ch in line)
    total = len(line)
    if letters < 3:
        return False
    if total and (letters / total) < 0.3:
        return False
    lower = line.lower()
    if digits and any(
        term in lower
        for term in [
            "street",
            "st",
            "road",
            "rd",
            "avenue",
            "ave",
            "drive",
            "dr",
            "lane",
            "ln",
            "suite",
            "ste",
            "way",
            "blvd",
        ]
    ):
        return False
    return digits <= max(2, letters // 2)


def _pick_name(lines):
    for line in lines:
        if _is_name_candidate(line) and len(line) <= 80:
            return line
    return lines[0] if lines else None


def _extract_po(lines):
    for line in lines:
        norm = normalize_text(line)
        if any(label in norm for label in _PO_LABELS):
            m = re.search(r"[A-Z0-9][A-Z0-9\\-]+", line)
            if m:
                return m.group(0)
    return None


def _extract_line_items(lines):
    items = []
    in_table = False
    for line in lines:
        norm = normalize_text(line)
        if ("qty" in norm or "quantity" in norm) and (
            "amount" in norm or "total" in norm or "price" in norm
        ):
            in_table = True
            continue
        if not in_table:
            continue
        if any(stop in norm for stop in ["subtotal", "sub total", "tax", "total"]):
            break
        item = _parse_item_line(line)
        if item:
            items.append(item)
    return items


def _parse_item_line(line):
    numbers = re.findall(r"[-\\d,.]+", line)
    amounts = [parse_amount(n) for n in numbers]
    amounts = [a for a in amounts if a is not None]
    if not amounts:
        return None
    qty = None
    for n in numbers:
        if re.fullmatch(r"\\d+", n):
            qty = int(n)
            break
    total = amounts[-1] if amounts else None
    unit_price = amounts[-2] if len(amounts) >= 2 else None
    desc = re.sub(r"[$€£]?[-\\d,.]+", "", line).strip()
    if not desc:
        return None
    return {
        "description": desc,
        "quantity": qty,
        "unit_price": unit_price,
        "total": total,
    }


def build_ground_truth():
    invoices = []
    for pdf_path in sorted(RAW_PDF_DIR.glob("*.pdf")):
        reader = PdfReader(str(pdf_path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        lines = _clean_lines(text)

        vendor_name, vendor_address = _extract_party(
            lines, ["from", "seller"], inline_labels=["from"]
        )
        customer_name, customer_address = _extract_party(
            lines,
            ["to", "bill to", "billed to", "sold to"],
            inline_labels=["sold to", "bill to", "billed to", "ship to", "to"],
            fallback_start=6,
        )

        invoice_date = _extract_date(lines, _DATE_LABELS, exclude_terms=["due"])
        due_date = _extract_date(lines, _DUE_LABELS, exclude_terms=["invoice"])
        po_number = _extract_po(lines)

        subtotal = _extract_amount(lines, _SUBTOTAL_LABELS)
        tax_amount = _extract_amount(lines, _TAX_LABELS, exclude_terms=["tax id", "taxid"])
        total_amount = _extract_amount(lines, _TOTAL_LABELS, exclude_terms=["subtotal"])

        line_items = _extract_line_items(lines)

        vendor_name = _clean_name(vendor_name)
        customer_name = _clean_name(customer_name)
        if not vendor_name:
            vendor_address = None
        if not customer_name:
            customer_address = None
        vendor_address = _clean_address(vendor_address)
        customer_address = _clean_address(customer_address)
        po_number = _clean_po(po_number)

        invoice_id = pdf_path.stem
        document_quality = 0.7 if invoice_id in SIMULATE_SCAN_IDS else 0.9

        invoices.append(
            {
                "invoice_id": invoice_id,
                "source_pdf": str(pdf_path.relative_to(ROOT_DIR)),
                "expected_data": {
                    "vendor_name": vendor_name,
                    "vendor_address": vendor_address,
                    "customer_name": customer_name,
                    "customer_address": customer_address,
                    "po_number": po_number,
                    "invoice_date": invoice_date,
                    "due_date": due_date,
                    "subtotal": subtotal,
                    "tax_amount": tax_amount,
                    "total_amount": total_amount,
                    "line_items": line_items,
                },
                "document_quality": document_quality,
            }
        )

    return {"invoices": invoices}


def _clean_name(value):
    if not value:
        return None
    if len(value) > 80:
        return None
    if any(ord(ch) < 32 for ch in value):
        return None
    norm = normalize_text(value)
    if any(
        term in norm
        for term in [
            "invoice",
            "subtotal",
            "total",
            "amount",
            "tax",
            "date",
            "charge",
            "payment",
            "balance",
            "due",
            "customer",
            "company name",
        ]
    ):
        return None
    if any(
        term in norm
        for term in [
            "street",
            "st",
            "road",
            "rd",
            "avenue",
            "ave",
            "blvd",
            "lane",
            "ln",
            "suite",
            "ste",
            "drive",
            "dr",
            "way",
            "city",
            "zip",
        ]
    ) and any(ch.isdigit() for ch in value):
        return None
    if not _is_name_candidate(value):
        return None
    return value


def _clean_address(value):
    if not value:
        return None
    norm = normalize_text(value)
    if len(norm) < 6:
        return None
    return value


def _clean_po(value):
    if not value:
        return None
    if not any(ch.isdigit() for ch in value):
        return None
    return value


def main():
    ground_truth = build_ground_truth()
    out_path = ROOT_DIR / "data" / "ground_truth.json"
    out_path.write_text(json.dumps(ground_truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {out_path}")


if __name__ == "__main__":
    main()
