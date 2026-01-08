import json
import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PIL import Image, ImageOps
import pytesseract

from src.preprocess.normalize import (
    normalize_text,
    ocr_confusion_normalize,
    parse_amount,
    parse_date,
)
from src.config import OCR_LANGS, RENDERED_DIR, TESSDATA_DIR, TESSERACT_CMD


_DATE_LABELS = ["invoice date", "inv date", "date"]
_DUE_LABELS = ["due date", "payment due", "due"]
_PO_LABELS = ["po number", "po#", "po", "p.o.", "purchase order", "order number"]
_SUBTOTAL_LABELS = ["subtotal", "sub total"]
_TAX_LABELS = ["tax", "vat"]
_TOTAL_LABELS = ["total due", "amount due", "balance due"]

_STOP_WORDS = [
    "bill to",
    "billed to",
    "ship to",
    "sold to",
    "to",
    "from",
    "date",
    "due",
    "total",
    "subtotal",
    "tax",
    "amount",
    "po",
    "order",
]

_NAME_STOP_TERMS = [
    "bill to",
    "billed to",
    "ship to",
    "sold to",
    "service address",
    "invoice",
    "invoice date",
    "due date",
    "balance due",
    "total",
    "subtotal",
    "tax",
    "payment",
    "customer id",
    "customer name",
    "terms",
]

_ADDRESS_STOP_TERMS = [
    "invoice",
    "balance due",
    "total",
    "subtotal",
    "tax",
    "payment",
    "due date",
    "invoice date",
    "terms",
]

_COMPANY_RE = re.compile(r"\b(inc|llc|ltd|co|company|corp|corporation)\b", re.IGNORECASE)


def _norm_line(text):
    return normalize_text(ocr_confusion_normalize(text))


def _norm_label(label):
    return normalize_text(ocr_confusion_normalize(label))


def _line_conf(line):
    if line.get("conf") is None:
        return None
    return float(line["conf"]) / 100.0


def _configure_tesseract():
    if TESSERACT_CMD and Path(TESSERACT_CMD).exists():
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)
    if TESSDATA_DIR and Path(TESSDATA_DIR).exists():
        os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)


def _resolve_langs():
    langs = OCR_LANGS
    if "vie" in OCR_LANGS:
        tess_vie = (TESSDATA_DIR / "vie.traineddata") if TESSDATA_DIR else None
        if not tess_vie or not tess_vie.exists():
            langs = "eng"
    return langs


def _bbox_union(lines):
    if not lines:
        return None
    x1 = min(l["x1"] for l in lines)
    y1 = min(l["y1"] for l in lines)
    x2 = max(l["x2"] for l in lines)
    y2 = max(l["y2"] for l in lines)
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def _extract_after_label(text, labels):
    norm = _norm_line(text)
    for label in labels:
        norm_label = _norm_label(label)
        if norm_label in norm:
            raw = text.strip()
            return raw or None
    return None


def _find_line(lines, labels):
    norm_labels = [_norm_label(label) for label in labels]
    for line in lines:
        norm = _norm_line(line["text"])
        if any(label in norm for label in norm_labels):
            return line
    return None


def _find_right_neighbor(lines, label_line, predicate):
    label_cy = (label_line["y1"] + label_line["y2"]) / 2
    label_h = max(1, label_line["y2"] - label_line["y1"])
    max_y_delta = max(12, int(label_h * 0.8))
    candidates = []
    for line in lines:
        if line is label_line:
            continue
        if line["x1"] <= label_line["x2"] + 10:
            continue
        line_cy = (line["y1"] + line["y2"]) / 2
        if abs(line_cy - label_cy) > max_y_delta:
            continue
        if not predicate(line["text"]):
            continue
        score = (-(abs(line_cy - label_cy)), line.get("conf") or 0.0)
        candidates.append((score, line))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_amount(lines, labels, exclude_terms=None):
    exclude_terms = exclude_terms or []
    norm_labels = [_norm_label(label) for label in labels]
    norm_excludes = [_norm_label(term) for term in exclude_terms]
    for line in lines:
        norm = _norm_line(line["text"])
        if not any(label in norm for label in norm_labels):
            continue
        if any(term in norm for term in norm_excludes):
            continue
        amt = _last_amount_in_line(line["text"])
        if amt is not None:
            return amt, _line_conf(line), _bbox_union([line])
        neighbor = _find_right_neighbor(
            lines, line, lambda text: _last_amount_in_line(text) is not None
        )
        if neighbor:
            amt = _last_amount_in_line(neighbor["text"])
            if amt is not None:
                return amt, _line_conf(neighbor), _bbox_union([neighbor])
    return None, None, None


def _extract_date(lines, labels, exclude_terms=None):
    exclude_terms = exclude_terms or []
    line = _find_line(lines, labels)
    if not line:
        return None, None, None
    norm = _norm_line(line["text"])
    if any(term in norm for term in exclude_terms):
        return None, None, None
    raw = _extract_after_label(line["text"], labels)
    if raw:
        parsed = _parse_date_from_text(raw)
        if parsed:
            return parsed, _line_conf(line), _bbox_union([line])
    parsed = _parse_date_from_text(line["text"])
    if parsed:
        return parsed, _line_conf(line), _bbox_union([line])
    neighbor = _find_right_neighbor(
        lines, line, lambda text: _parse_date_from_text(text) is not None
    )
    if neighbor:
        parsed = _parse_date_from_text(neighbor["text"])
        if parsed:
            return parsed, _line_conf(neighbor), _bbox_union([neighbor])
    return None, None, None


def _parse_date_from_text(text):
    patterns = [
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\s+\d{1,2},\s+\d{4}\b",
        r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\w*\s+\d{4}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            parsed = parse_date(match.group(0))
            if parsed and 1900 <= parsed.year <= 2100:
                return parsed.isoformat()
    parsed = parse_date(text)
    if parsed and 1900 <= parsed.year <= 2100:
        return parsed.isoformat()
    return None


def _last_amount_in_line(line):
    candidates = re.findall(r"[$€£]?\s*[\d,.\(\)-]+", line)
    for raw in reversed(candidates):
        val = parse_amount(raw)
        if val is not None:
            return val
    return None


def _last_amount_with_raw(line):
    candidates = re.findall(r"[$â‚¬Â£]?\s*[\d,.\(\)-]+", line)
    for raw in reversed(candidates):
        val = parse_amount(raw)
        if val is not None:
            return raw, val
    return None, None


def _extract_amount_candidates(lines, labels, exclude_terms=None):
    exclude_terms = exclude_terms or []
    norm_labels = [_norm_label(label) for label in labels]
    norm_excludes = [_norm_label(term) for term in exclude_terms]
    candidates = []
    for line in lines:
        norm = _norm_line(line["text"])
        if not any(label in norm for label in norm_labels):
            continue
        if any(term in norm for term in norm_excludes):
            continue
        raw, amt = _last_amount_with_raw(line["text"])
        if amt is None or raw is None:
            continue
        has_decimal = bool(re.search(r"\d+[.,]\d{1,2}\b", raw))
        candidates.append(
            {
                "amount": amt,
                "conf": _line_conf(line),
                "bbox": _bbox_union([line]),
                "has_decimal": has_decimal,
            }
        )
    return candidates


def _pick_best_amount(candidates):
    return max(candidates, key=lambda c: (c["conf"] or 0.0, c["amount"]))


def _extract_total_amount(lines):
    candidates = _extract_amount_candidates(
        lines,
        _TOTAL_LABELS,
        exclude_terms=["subtotal", "sub total"],
    )
    positive = [c for c in candidates if c["amount"] > 0]
    with_decimal = [c for c in positive if c["has_decimal"]]
    if with_decimal or positive:
        chosen = _pick_best_amount(with_decimal or positive)
        return chosen["amount"], chosen["conf"], chosen["bbox"]

    fallback = _extract_amount_candidates(
        lines,
        ["total"],
        exclude_terms=["subtotal", "sub total", "tax"],
    )
    fallback = [c for c in fallback if c["amount"] > 0 and c["has_decimal"]]
    if not fallback:
        return None, None, None
    chosen = _pick_best_amount(fallback)
    return chosen["amount"], chosen["conf"], chosen["bbox"]


def _lines_from_tess_data(data, scale, offset_x, offset_y):
    line_buckets = {}
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf_raw = data["conf"][i]
        conf = float(conf_raw) if conf_raw != "-1" else None
        left = int(data["left"][i])
        top = int(data["top"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])
        token = {
            "text": text,
            "conf": conf,
            "x1": left,
            "y1": top,
            "x2": left + width,
            "y2": top + height,
            "line_num": int(data["line_num"][i]),
            "block_num": int(data["block_num"][i]),
            "par_num": int(data["par_num"][i]),
        }
        line_key = (token["block_num"], token["par_num"], token["line_num"])
        line_buckets.setdefault(line_key, []).append(token)

    lines = []
    for items in line_buckets.values():
        items = sorted(items, key=lambda t: t["x1"])
        text = " ".join(t["text"] for t in items)
        x1 = min(t["x1"] for t in items) / scale + offset_x
        y1 = min(t["y1"] for t in items) / scale + offset_y
        x2 = max(t["x2"] for t in items) / scale + offset_x
        y2 = max(t["y2"] for t in items) / scale + offset_y
        confs = [t["conf"] for t in items if t["conf"] is not None]
        avg_conf = sum(confs) / len(confs) if confs else None
        lines.append(
            {
                "text": text,
                "conf": avg_conf,
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2),
            }
        )
    return lines


def _ocr_lines_threshold(image_path, threshold=150):
    img = Image.open(image_path)
    gray = ImageOps.autocontrast(ImageOps.grayscale(img))
    bw = gray.point(lambda p: 0 if p < threshold else 255)
    data = pytesseract.image_to_data(
        bw,
        lang=_resolve_langs(),
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )
    return _lines_from_tess_data(data, 1, 0, 0)


def _extract_amounts_from_totals_block(image_path, total_bbox):
    if not image_path or not total_bbox:
        return None, None, None, None
    img = Image.open(image_path)
    x1 = max(0, total_bbox["x1"] - 300)
    x2 = min(img.size[0], total_bbox["x2"] + 50)
    y1 = max(0, total_bbox["y1"] - 260)
    y2 = min(img.size[1], total_bbox["y2"] + 20)
    if x2 <= x1 or y2 <= y1:
        return None, None, None, None

    crop = img.crop((x1, y1, x2, y2))
    gray = ImageOps.autocontrast(ImageOps.grayscale(crop))
    bw = gray.point(lambda p: 0 if p < 150 else 255)
    data = pytesseract.image_to_data(
        bw,
        lang=_resolve_langs(),
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )
    lines = _lines_from_tess_data(data, 1, x1, y1)
    sub_val, sub_conf, sub_bbox = _extract_amount(lines, _SUBTOTAL_LABELS)
    tax_val, tax_conf, tax_bbox = _extract_amount(
        lines, _TAX_LABELS, exclude_terms=["tax id", "taxid"]
    )
    return sub_val, sub_conf, sub_bbox, tax_val, tax_conf, tax_bbox


def _extract_left_column_address_from_tokens(tokens, label_line, page_width):
    if not tokens or not label_line or not page_width:
        return None, None, None
    split_x = int(page_width * 0.5)
    label_h = max(1, label_line["y2"] - label_line["y1"])
    y_min = label_line["y2"] - int(label_h * 0.1)
    y_max = label_line["y2"] + int(label_h * 5)
    filtered = [
        t
        for t in tokens
        if t["x1"] < split_x and t["y1"] >= y_min and t["y1"] <= y_max
    ]
    if not filtered:
        return None, None, None

    line_buckets = {}
    for t in filtered:
        line_key = (t.get("block_num"), t.get("par_num"), t.get("line_num"))
        line_buckets.setdefault(line_key, []).append(t)

    lines = []
    for items in line_buckets.values():
        items = sorted(items, key=lambda t: t["x1"])
        text = " ".join(t["text"] for t in items)
        x1 = min(t["x1"] for t in items)
        y1 = min(t["y1"] for t in items)
        x2 = max(t["x2"] for t in items)
        y2 = max(t["y2"] for t in items)
        confs = [t["conf"] for t in items if t.get("conf") is not None]
        avg_conf = (sum(confs) / len(confs) / 100.0) if confs else None
        lines.append({"text": text, "conf": avg_conf, "x1": x1, "y1": y1, "x2": x2, "y2": y2})

    lines = sorted(lines, key=lambda l: (l["y1"], l["x1"]))
    addr_lines = [l for l in lines if _is_address_candidate(l["text"])]
    if not addr_lines:
        return None, None, None
    addr_lines = addr_lines[:2]
    address = ", ".join(l["text"] for l in addr_lines)
    confs = [l["conf"] for l in addr_lines if l["conf"] is not None]
    avg_conf = sum(confs) / len(confs) if confs else None
    bbox = _bbox_union(addr_lines)
    return address, avg_conf, bbox


def _extract_tax_from_crop(invoice_id, subtotal_bbox, total_bbox):
    image_path = RENDERED_DIR / f"{invoice_id}_p1.png"
    if not image_path.exists():
        return None, None, None

    x1 = min(subtotal_bbox["x1"], total_bbox["x1"]) - 80
    x2 = max(subtotal_bbox["x2"], total_bbox["x2"]) + 80
    y1 = subtotal_bbox["y2"] - 5
    y2 = total_bbox["y1"] + 30
    if x2 <= x1 or y2 <= y1:
        return None, None, None

    img = Image.open(image_path)
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(img.size[0], x2)
    y2 = min(img.size[1], y2)
    if x2 <= x1 or y2 <= y1:
        return None, None, None

    crop = img.crop((x1, y1, x2, y2))
    scale = 2
    crop = crop.resize((crop.size[0] * scale, crop.size[1] * scale))
    data = pytesseract.image_to_data(
        crop,
        lang=_resolve_langs(),
        output_type=pytesseract.Output.DICT,
        config="--psm 6",
    )
    lines = _lines_from_tess_data(data, scale, x1, y1)
    for line in lines:
        norm = _norm_line(line["text"])
        if "tax" not in norm:
            continue
        amt = _last_amount_in_line(line["text"])
        if amt is None:
            continue
        return amt, _line_conf(line), _bbox_union([line])
    return None, None, None


def _extract_po(lines):
    line = _find_line(lines, _PO_LABELS)
    if not line:
        return None, None, None
    tokens = re.findall(r"[A-Z0-9][A-Z0-9\\-]+", line["text"])
    if tokens:
        with_digits = [t for t in tokens if any(ch.isdigit() for ch in t)]
        value = with_digits[-1] if with_digits else tokens[-1]
        return value, _line_conf(line), _bbox_union([line])
    neighbor = _find_right_neighbor(
        lines,
        line,
        lambda text: bool(re.search(r"[A-Z0-9][A-Z0-9\\-]+", text))
        and any(ch.isdigit() for ch in text),
    )
    if neighbor:
        tokens = re.findall(r"[A-Z0-9][A-Z0-9\\-]+", neighbor["text"])
        with_digits = [t for t in tokens if any(ch.isdigit() for ch in t)]
        value = with_digits[-1] if with_digits else tokens[-1]
        return value, _line_conf(neighbor), _bbox_union([neighbor])
    return None, None, None


def _extract_block(lines, start_keywords):
    for idx, line in enumerate(lines):
        norm = _norm_line(line["text"])
        if any(_starts_with_label(norm, keyword) for keyword in start_keywords):
            block = []
            for nxt in lines[idx + 1 :]:
                nxt_norm = _norm_line(nxt["text"])
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
        inline = _extract_inline_value(line["text"], inline_labels)
        if inline:
            if not _is_name_candidate(inline):
                break
            address_lines = _collect_address(lines[idx + 1 :])
            address = (
                ", ".join([b["text"] for b in address_lines[:2]])
                if address_lines
                else None
            )
            name_conf = _line_conf(line)
            addr_confs = [c for c in (_line_conf(b) for b in address_lines) if c is not None]
            address_conf = sum(addr_confs) / len(addr_confs) if addr_confs else None
            name_bbox = _bbox_union([line])
            address_bbox = _bbox_union(address_lines) if address_lines else None
            return inline, address, name_conf, address_conf, name_bbox, address_bbox

    block = _extract_block(lines, start_keywords)
    if block:
        name = _pick_name([b["text"] for b in block])
        name_line = next((b for b in block if b["text"] == name), block[0])
        address_lines = [b for b in block if b["text"] != name]
        address = (
            ", ".join([b["text"] for b in address_lines[:2]])
            if address_lines
            else None
        )
        name_conf = _line_conf(name_line)
        addr_confs = [c for c in (_line_conf(b) for b in address_lines) if c is not None]
        address_conf = sum(addr_confs) / len(addr_confs) if addr_confs else None
        name_bbox = _bbox_union([name_line])
        address_bbox = _bbox_union(address_lines) if address_lines else None
        return name or None, address or None, name_conf, address_conf, name_bbox, address_bbox

    company_line = _find_company_line(lines)
    if company_line:
        return (
            company_line["text"],
            None,
            _line_conf(company_line),
            None,
            _bbox_union([company_line]),
            None,
        )

    fallback = lines[fallback_start : fallback_start + 4]
    if not fallback:
        return None, None, None, None, None, None
    name = _pick_name([b["text"] for b in fallback])
    name_line = next((b for b in fallback if b["text"] == name), fallback[0])
    address_lines = [b for b in fallback if b["text"] != name]
    address = (
        ", ".join([b["text"] for b in address_lines[:2]])
        if address_lines
        else None
    )
    name_conf = _line_conf(name_line)
    addr_confs = [c for c in (_line_conf(b) for b in address_lines) if c is not None]
    address_conf = sum(addr_confs) / len(addr_confs) if addr_confs else None
    name_bbox = _bbox_union([name_line])
    address_bbox = _bbox_union(address_lines) if address_lines else None
    return name or None, address or None, name_conf, address_conf, name_bbox, address_bbox


def _extract_inline_value(line, labels):
    for label in labels:
        m = re.match(rf"{re.escape(label)}\s*:?\s*(.+)$", line, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _is_address_candidate(line):
    if not line:
        return False
    letters = sum(ch.isalpha() for ch in line)
    if letters < 3:
        return False
    if re.search(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", line):
        return False
    if re.search(r"[$â‚¬Â£]\s*[\d,]+", line):
        return False
    if len(line) < 6:
        return False
    lower = line.lower()
    street_terms = ("street", "st", "road", "rd", "avenue", "ave", "suite", "ste", "way", "blvd", "lane", "ln", "drive", "dr")
    digits = sum(ch.isdigit() for ch in line)
    if digits >= 2 or "," in line:
        return True
    if digits >= 1 and (any(term in lower for term in street_terms) or line.strip()[0].isdigit()):
        return True
    return False


def _find_label_line(lines, labels):
    candidates = []
    norm_labels = [_norm_label(label) for label in labels]
    for line in lines:
        norm = _norm_line(line["text"])
        if any(_starts_with_label(norm, label) for label in norm_labels):
            candidates.append(line)
    if not candidates:
        return None
    return sorted(candidates, key=lambda l: (l["x1"], l["y1"]))[0]


def _find_address_invoice_for_line(lines):
    for line in lines:
        norm = _norm_line(line["text"])
        if "address" in norm and "invoice for" in norm:
            return line
    return None


def _extract_party_from_label_column(lines, label_line, labels):
    if not label_line:
        return None, None, None, None, None, None
    width = max(l["x2"] for l in lines) if lines else 0
    col_right = label_line["x1"] + max(200, int(width * 0.35))
    label_cy = (label_line["y1"] + label_line["y2"]) / 2
    label_h = max(1, label_line["y2"] - label_line["y1"])
    right_candidates = [
        l
        for l in lines
        if l["x1"] > label_line["x2"]
        and abs(((l["y1"] + l["y2"]) / 2) - label_cy) <= (label_h * 0.6)
    ]
    if right_candidates:
        right_x1 = min(l["x1"] for l in right_candidates)
        col_right = min(col_right, int((label_line["x2"] + right_x1) / 2))

    inline = _extract_inline_value(label_line["text"], labels)
    name_line = None
    name = None
    if inline and _is_name_candidate(inline):
        name = inline
        name_line = label_line

    min_y = label_line["y1"] + int(label_h * 0.2)
    max_y = label_line["y2"] + int(label_h * 5)
    candidates = [
        l
        for l in lines
        if l["y1"] >= min_y and l["y1"] <= max_y and l["x1"] <= col_right
    ]
    candidates = sorted(candidates, key=lambda l: (l["y1"], l["x1"]))
    candidates = [
        l
        for l in candidates
        if not any(_starts_with_label(_norm_line(l["text"]), stop) for stop in _STOP_WORDS)
    ]

    if not name and candidates:
        name_line = next(
            (l for l in candidates if _is_name_candidate(l["text"])), candidates[0]
        )
        name = name_line["text"]

    address_lines = []
    if name_line:
        for l in candidates:
            if l is name_line:
                continue
            if _is_address_candidate(l["text"]):
                address_lines.append(l)
            if len(address_lines) >= 2:
                break

    address = ", ".join(l["text"] for l in address_lines) if address_lines else None
    name_conf = _line_conf(name_line) if name_line else None
    addr_confs = [c for c in (_line_conf(l) for l in address_lines) if c is not None]
    address_conf = sum(addr_confs) / len(addr_confs) if addr_confs else None
    name_bbox = _bbox_union([name_line]) if name_line else None
    address_bbox = _bbox_union(address_lines) if address_lines else None
    return name, address, name_conf, address_conf, name_bbox, address_bbox


def _collect_address(lines):
    collected = []
    for nxt in lines:
        nxt_norm = _norm_line(nxt["text"])
        if any(_starts_with_label(nxt_norm, stop) for stop in _STOP_WORDS):
            break
        collected.append(nxt)
    return collected


def _find_company_line(lines):
    for line in reversed(lines):
        if _COMPANY_RE.search(line["text"]) and _is_name_candidate(line["text"]):
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
    parts = [desc]
    if qty is not None:
        parts.append(f"Qty: {qty}")
    if unit_price is not None:
        parts.append(f"Price: ${unit_price:.2f}")
    if total is not None:
        parts.append(f"Total: ${total:.2f}")
    return "\n".join(parts)


def _extract_line_items(lines):
    items = []
    item_lines = []
    in_table = False
    for line in lines:
        norm = _norm_line(line["text"])
        if ("qty" in norm or "quantity" in norm) and (
            "amount" in norm or "total" in norm or "price" in norm
        ):
            in_table = True
            continue
        if not in_table:
            continue
        if any(stop in norm for stop in ["subtotal", "sub total", "tax", "total"]):
            break
        text = _parse_item_line(line["text"])
        if text:
            items.append({"text": text})
            item_lines.append(line)
    bbox = _bbox_union(item_lines) if item_lines else None
    confs = [c for c in (_line_conf(l) for l in item_lines) if c is not None]
    avg_conf = sum(confs) / len(confs) if confs else None
    return items, avg_conf, bbox


def build_ocr_results():
    _configure_tesseract()
    raw_path = ROOT_DIR / "outputs" / "ocr_raw.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    results = {}

    for inv_id, inv_data in raw.items():
        pages = inv_data.get("pages", [])
        lines = []
        tokens = []
        page_width = None
        for page in pages:
            lines.extend(page.get("lines", []))
            tokens.extend(page.get("tokens", []))
            if page_width is None:
                page_width = page.get("width")

        (
            vendor_name,
            vendor_address,
            vendor_name_conf,
            vendor_address_conf,
            vendor_name_bbox,
            vendor_address_bbox,
        ) = _extract_party(
            lines, ["from", "seller"], inline_labels=["from"]
        )
        (
            customer_name,
            customer_address,
            customer_name_conf,
            customer_address_conf,
            customer_name_bbox,
            customer_address_bbox,
        ) = _extract_party(
            lines,
            ["to", "bill to", "billed to", "sold to"],
            inline_labels=["sold to", "bill to", "billed to", "ship to", "to"],
            fallback_start=6,
        )

        po_number, po_conf, po_bbox = _extract_po(lines)
        invoice_date, invoice_conf, invoice_bbox = _extract_date(
            lines, _DATE_LABELS, exclude_terms=["due"]
        )
        due_date, due_conf, due_bbox = _extract_date(
            lines, _DUE_LABELS, exclude_terms=["invoice"]
        )

        subtotal, subtotal_conf, subtotal_bbox = _extract_amount(
            lines, _SUBTOTAL_LABELS
        )
        tax_amount, tax_conf, tax_bbox = _extract_amount(
            lines, _TAX_LABELS, exclude_terms=["tax id", "taxid"]
        )
        total_amount, total_conf, total_bbox = _extract_total_amount(lines)

        fallback_lines = None
        image_path = RENDERED_DIR / f"{inv_id}_p1.png"
        name_valid = bool(customer_name and _is_name_candidate(customer_name))
        needs_fallback = (
            subtotal is None
            or tax_amount is None
            or total_amount is None
            or customer_address is None
            or not name_valid
        )
        if needs_fallback and image_path.exists():
            fallback_lines = _ocr_lines_threshold(image_path, threshold=150)

        if subtotal is None and fallback_lines:
            subtotal, subtotal_conf, subtotal_bbox = _extract_amount(
                fallback_lines, _SUBTOTAL_LABELS
            )

        if tax_amount is None and fallback_lines:
            tax_amount, tax_conf, tax_bbox = _extract_amount(
                fallback_lines, _TAX_LABELS, exclude_terms=["tax id", "taxid"]
            )

        if total_amount is None and fallback_lines:
            total_amount, total_conf, total_bbox = _extract_total_amount(
                fallback_lines
            )

        if (subtotal is None or tax_amount is None) and total_bbox and image_path.exists():
            sub_val, sub_conf, sub_bbox, tax_val, tax_conf2, tax_bbox2 = _extract_amounts_from_totals_block(
                image_path, total_bbox
            )
            if subtotal is None and sub_val is not None:
                subtotal, subtotal_conf, subtotal_bbox = sub_val, sub_conf, sub_bbox
            if tax_amount is None and tax_val is not None:
                tax_amount, tax_conf, tax_bbox = tax_val, tax_conf2, tax_bbox2

        if tax_amount is None and subtotal_bbox and total_bbox:
            tax_amount, tax_conf, tax_bbox = _extract_tax_from_crop(
                inv_id, subtotal_bbox, total_bbox
            )

        customer_labels = ["bill to", "billed to", "sold to", "to"]
        alt_customer_labels = ["address", "invoice for"]
        if customer_address is None or not name_valid:
            label_line = _find_label_line(lines, customer_labels)
            if not label_line:
                label_line = _find_address_invoice_for_line(lines)
                if label_line:
                    customer_labels = alt_customer_labels
            source_lines = lines
            if not label_line and fallback_lines:
                label_line = _find_label_line(fallback_lines, customer_labels)
                if not label_line:
                    label_line = _find_address_invoice_for_line(fallback_lines)
                    if label_line:
                        customer_labels = alt_customer_labels
                source_lines = fallback_lines
            if label_line:
                (
                    cust_name2,
                    cust_addr2,
                    cust_name_conf2,
                    cust_addr_conf2,
                    cust_name_bbox2,
                    cust_addr_bbox2,
                ) = _extract_party_from_label_column(
                    source_lines, label_line, customer_labels
                )
                norm_label = _norm_line(label_line["text"])
                if "address" in norm_label and "invoice for" in norm_label:
                    addr_from_tokens, addr_conf, addr_bbox = _extract_left_column_address_from_tokens(
                        tokens, label_line, page_width
                    )
                    if addr_from_tokens:
                        cust_addr2 = addr_from_tokens
                        cust_addr_conf2 = addr_conf
                        cust_addr_bbox2 = addr_bbox
                if cust_name2:
                    customer_name = cust_name2
                    customer_name_conf = cust_name_conf2
                    customer_name_bbox = cust_name_bbox2
                    name_valid = _is_name_candidate(customer_name)
                if cust_addr2:
                    customer_address = cust_addr2
                    customer_address_conf = cust_addr_conf2
                    customer_address_bbox = cust_addr_bbox2

        line_items, line_conf, line_bbox = _extract_line_items(lines)

        structured_data = {
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
        }

        confidence_scores = {
            "vendor_name": vendor_name_conf,
            "vendor_address": vendor_address_conf,
            "customer_name": customer_name_conf,
            "customer_address": customer_address_conf,
            "po_number": po_conf,
            "invoice_date": invoice_conf,
            "due_date": due_conf,
            "subtotal": subtotal_conf,
            "tax_amount": tax_conf,
            "total_amount": total_conf,
            "line_items": line_conf,
        }

        bounding_boxes = {
            "vendor_name": vendor_name_bbox,
            "vendor_address": vendor_address_bbox,
            "customer_name": customer_name_bbox,
            "customer_address": customer_address_bbox,
            "po_number": po_bbox,
            "invoice_date": invoice_bbox,
            "due_date": due_bbox,
            "subtotal": subtotal_bbox,
            "tax_amount": tax_bbox,
            "total_amount": total_bbox,
            "line_items": line_bbox,
        }

        results[inv_id] = {
            "raw_text": inv_data.get("raw_text", ""),
            "structured_data": structured_data,
            "confidence_scores": confidence_scores,
            "bounding_boxes": bounding_boxes,
        }

    return results


def main():
    results = build_ocr_results()
    out_path = ROOT_DIR / "data" / "ocr_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {out_path}")


if __name__ == "__main__":
    main()
