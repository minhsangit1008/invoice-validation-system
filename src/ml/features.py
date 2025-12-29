from datetime import date

from src.config import (
    ADDRESS_FUZZY_PASS,
    AMOUNT_ABS_PASS,
    AMOUNT_REL_PASS,
    DATE_PASS_DAYS,
    FUZZY_PASS,
)
from src.match.fuzzy import fuzzy_score
from src.preprocess.normalize import (
    normalize_address,
    normalize_company_suffix,
    ocr_confusion_normalize,
    parse_amount,
    parse_date,
)

FIELD_TYPE_MAP = {
    "vendor_name": "name",
    "customer_name": "name",
    "vendor_address": "address",
    "customer_address": "address",
    "po_number": "id",
    "invoice_date": "date",
    "due_date": "date",
    "subtotal": "amount",
    "tax_amount": "amount",
    "total_amount": "amount",
}


def extract_features(field, expected, detected, ocr_conf):
    expected_str = "" if expected is None else str(expected)
    detected_str = "" if detected is None else str(detected)
    detected_len = len(detected_str)
    digit_ratio = _digit_ratio(detected_str)
    has_confusable = int(any(ch in "O0I1lS5B8" for ch in detected_str))

    features = {
        "field_name": field,
        "field_type": FIELD_TYPE_MAP.get(field, "other"),
        "ocr_conf": float(ocr_conf) if ocr_conf is not None else 0.0,
        "detected_len": detected_len,
        "digit_ratio": digit_ratio,
        "has_confusable": has_confusable,
        "is_missing": int(detected is None or detected_str.strip() == ""),
    }

    if FIELD_TYPE_MAP.get(field) in ("name", "address"):
        normalizer = normalize_company_suffix if FIELD_TYPE_MAP[field] == "name" else normalize_address
        f_score, _ = fuzzy_score(expected_str, detected_str, normalizer=normalizer)
        features["fuzzy_score"] = f_score
    else:
        features["fuzzy_score"] = 0.0

    if FIELD_TYPE_MAP.get(field) == "amount":
        exp_amt = parse_amount(expected)
        det_amt = parse_amount(detected)
        if exp_amt is not None and det_amt is not None:
            diff = abs(exp_amt - det_amt)
            rel = diff / exp_amt if exp_amt else diff
            features["abs_diff"] = diff
            features["rel_diff"] = rel
        else:
            features["abs_diff"] = 0.0
            features["rel_diff"] = 0.0
    else:
        features["abs_diff"] = 0.0
        features["rel_diff"] = 0.0

    if FIELD_TYPE_MAP.get(field) == "date":
        exp_date = parse_date(expected)
        det_date = parse_date(detected)
        if isinstance(exp_date, date) and isinstance(det_date, date):
            features["days_diff"] = abs((exp_date - det_date).days)
        else:
            features["days_diff"] = 0.0
    else:
        features["days_diff"] = 0.0

    return features


def label_is_wrong(field, expected, detected):
    if expected is None and detected in (None, ""):
        return 0
    ftype = FIELD_TYPE_MAP.get(field, "other")

    if ftype == "id":
        exp = ocr_confusion_normalize(expected)
        det = ocr_confusion_normalize(detected)
        return int(exp != det)

    if ftype == "name":
        score, _ = fuzzy_score(expected, detected, normalizer=normalize_company_suffix)
        return int(score < FUZZY_PASS)

    if ftype == "address":
        score, _ = fuzzy_score(expected, detected, normalizer=normalize_address)
        return int(score < ADDRESS_FUZZY_PASS)

    if ftype == "date":
        exp_date = parse_date(expected)
        det_date = parse_date(detected)
        if exp_date is None or det_date is None:
            return 1
        return int(abs((exp_date - det_date).days) > DATE_PASS_DAYS)

    if ftype == "amount":
        exp_amt = parse_amount(expected)
        det_amt = parse_amount(detected)
        if exp_amt is None or det_amt is None:
            return 1
        diff = abs(exp_amt - det_amt)
        rel = diff / exp_amt if exp_amt else diff
        return int(diff > AMOUNT_ABS_PASS and rel > AMOUNT_REL_PASS)

    return int(str(expected).strip() != str(detected).strip())


def build_training_rows(ground_truth, ocr_results):
    rows = []
    for inv in ground_truth.get("invoices", []):
        inv_id = inv.get("invoice_id")
        expected = inv.get("expected_data", {})
        ocr = ocr_results.get(inv_id, {})
        structured = ocr.get("structured_data", {})
        ocr_conf = ocr.get("confidence_scores", {})
        for field in FIELD_TYPE_MAP.keys():
            features = extract_features(
                field,
                expected.get(field),
                structured.get(field),
                ocr_conf.get(field),
            )
            label = label_is_wrong(field, expected.get(field), structured.get(field))
            rows.append((features, label, inv_id, field))
    return rows


def _digit_ratio(text):
    if not text:
        return 0.0
    digits = sum(ch.isdigit() for ch in text)
    return digits / len(text)
