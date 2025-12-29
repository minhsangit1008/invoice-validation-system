from src.config import (
    ADDRESS_FUZZY_PASS,
    ADDRESS_FUZZY_WARN,
    AMOUNT_ABS_PASS,
    AMOUNT_ABS_WARN,
    AMOUNT_REL_PASS,
    AMOUNT_REL_WARN,
    CONFIDENCE_REVIEW_THRESHOLD,
    DATE_PASS_DAYS,
    DATE_WARN_DAYS,
    FUZZY_PASS,
    FUZZY_WARN,
    NAME_TRUNCATE_MIN_LEN,
    NAME_TRUNCATE_RATIO,
    STATUS_ON_CRITICAL,
)
from src.match.fuzzy import fuzzy_score
from src.ml.predict import predict_p_wrong
from src.ml.features import FIELD_TYPE_MAP
from src.output.notifications import build_discrepancy
from src.preprocess.normalize import (
    normalize_address,
    normalize_company_suffix,
    ocr_confusion_normalize,
    parse_amount,
    parse_date,
)
from src.rules.line_items import validate_line_items
from src.scoring.confidence import compute_overall_confidence


def validate_invoice(ocr_data, ground_truth, database, model_bundle=None):
    expected = ground_truth.get("expected_data", {})
    structured = ocr_data.get("structured_data", {})
    ocr_conf = ocr_data.get("confidence_scores", {})
    bboxes = ocr_data.get("bounding_boxes", {})

    discrepancies = []
    details = {"fuzzy_scores": {}, "amount_diffs": {}, "date_diffs": {}}

    _check_id_field(
        "po_number",
        expected.get("po_number"),
        structured.get("po_number"),
        ocr_conf.get("po_number"),
        bboxes,
        discrepancies,
    )

    _check_fuzzy_field(
        "vendor_name",
        expected.get("vendor_name"),
        structured.get("vendor_name"),
        ocr_conf.get("vendor_name"),
        bboxes,
        discrepancies,
        details["fuzzy_scores"],
        normalize_company_suffix,
        FUZZY_PASS,
        FUZZY_WARN,
        allow_truncate=True,
    )

    _check_fuzzy_field(
        "customer_name",
        expected.get("customer_name"),
        structured.get("customer_name"),
        ocr_conf.get("customer_name"),
        bboxes,
        discrepancies,
        details["fuzzy_scores"],
        normalize_company_suffix,
        FUZZY_PASS,
        FUZZY_WARN,
        allow_truncate=True,
    )

    _check_fuzzy_field(
        "vendor_address",
        expected.get("vendor_address"),
        structured.get("vendor_address"),
        ocr_conf.get("vendor_address"),
        bboxes,
        discrepancies,
        details["fuzzy_scores"],
        normalize_address,
        ADDRESS_FUZZY_PASS,
        ADDRESS_FUZZY_WARN,
        missing_severity="warning",
    )

    _check_fuzzy_field(
        "customer_address",
        expected.get("customer_address"),
        structured.get("customer_address"),
        ocr_conf.get("customer_address"),
        bboxes,
        discrepancies,
        details["fuzzy_scores"],
        normalize_address,
        ADDRESS_FUZZY_PASS,
        ADDRESS_FUZZY_WARN,
        missing_severity="warning",
    )

    _check_date_field(
        "invoice_date",
        expected.get("invoice_date"),
        structured.get("invoice_date"),
        ocr_conf.get("invoice_date"),
        bboxes,
        discrepancies,
        details["date_diffs"],
    )

    _check_date_field(
        "due_date",
        expected.get("due_date"),
        structured.get("due_date"),
        ocr_conf.get("due_date"),
        bboxes,
        discrepancies,
        details["date_diffs"],
    )

    _check_amount_field(
        "subtotal",
        expected.get("subtotal"),
        structured.get("subtotal"),
        ocr_conf.get("subtotal"),
        bboxes,
        discrepancies,
        details["amount_diffs"],
    )

    _check_amount_field(
        "tax_amount",
        expected.get("tax_amount"),
        structured.get("tax_amount"),
        ocr_conf.get("tax_amount"),
        bboxes,
        discrepancies,
        details["amount_diffs"],
    )

    _check_amount_field(
        "total_amount",
        expected.get("total_amount"),
        structured.get("total_amount"),
        ocr_conf.get("total_amount"),
        bboxes,
        discrepancies,
        details["amount_diffs"],
    )

    po_number = structured.get("po_number") or expected.get("po_number")
    po_record = database.get("purchase_orders", {}).get(po_number, {})
    if not po_record and structured.get("po_number"):
        norm_po = ocr_confusion_normalize(structured.get("po_number"))
        for key, rec in database.get("purchase_orders", {}).items():
            if ocr_confusion_normalize(key) == norm_po:
                po_record = rec
                break
    line_discrepancies, parsed_items = validate_line_items(
        structured.get("line_items"),
        expected.get("line_items"),
        po_record,
        bboxes,
    )
    discrepancies.extend(line_discrepancies)
    details["parsed_line_items"] = parsed_items

    p_wrong_by_field = _predict_p_wrong(
        model_bundle,
        expected,
        structured,
        ocr_conf,
    )

    confidence_score, field_scores, base_score, penalty = compute_overall_confidence(
        ocr_conf, discrepancies, p_wrong_by_field
    )
    details["field_scores"] = field_scores
    details["base_score"] = base_score
    details["penalty"] = penalty
    details["p_wrong_by_field"] = p_wrong_by_field

    status = _decide_status(discrepancies, confidence_score)

    return {
        "status": status,
        "discrepancies": discrepancies,
        "confidence_score": confidence_score,
        "validation_details": details,
    }


def _predict_p_wrong(model_bundle, expected, structured, ocr_conf):
    p_wrong_by_field = {}
    for field in FIELD_TYPE_MAP.keys():
        p_wrong_by_field[field] = predict_p_wrong(
            model_bundle,
            field,
            expected.get(field),
            structured.get(field),
            ocr_conf.get(field),
        )
    return p_wrong_by_field


def _check_id_field(field, expected, detected, conf, bboxes, discrepancies):
    expected_norm = ocr_confusion_normalize(expected)
    detected_norm = ocr_confusion_normalize(detected)
    if expected is None and detected is None:
        return
    if expected_norm == detected_norm:
        if str(expected).strip() != str(detected).strip():
            discrepancies.append(
                build_discrepancy(
                    field,
                    "warning",
                    expected,
                    detected,
                    conf or 0.8,
                    "Check OCR confusable characters (O/0, I/1)",
                    bboxes.get(field),
                )
            )
        return
    discrepancies.append(
        build_discrepancy(
            field,
            "critical",
            expected,
            detected,
            conf or 0.8,
            "PO mismatch",
            bboxes.get(field),
        )
    )


def _check_fuzzy_field(
    field,
    expected,
    detected,
    conf,
    bboxes,
    discrepancies,
    fuzzy_scores,
    normalizer,
    pass_th,
    warn_th,
    allow_truncate=False,
    missing_severity="critical",
):
    expected_norm = normalizer(expected) if expected is not None else ""
    detected_norm = normalizer(detected) if detected is not None else ""
    if expected_norm and not detected_norm:
        discrepancies.append(
            build_discrepancy(
                field,
                missing_severity,
                expected,
                detected,
                conf or 0.6,
                "Missing value",
                bboxes.get(field),
            )
        )
        return

    score, method = fuzzy_score(expected, detected, normalizer=normalizer)
    fuzzy_scores[field] = {"score": score, "method": method}
    if score >= pass_th:
        return
    if score >= warn_th:
        discrepancies.append(
            build_discrepancy(
                field,
                "warning",
                expected,
                detected,
                conf or 0.7,
                "Possible abbreviation or truncation",
                bboxes.get(field),
            )
        )
        return
    if allow_truncate and _is_truncated_match(expected_norm, detected_norm):
        discrepancies.append(
            build_discrepancy(
                field,
                "warning",
                expected,
                detected,
                conf or 0.7,
                "Likely truncated",
                bboxes.get(field),
            )
        )
        return
    discrepancies.append(
        build_discrepancy(
            field,
            "critical",
            expected,
            detected,
            conf or 0.7,
            "Low similarity",
            bboxes.get(field),
        )
    )


def _is_truncated_match(expected_norm, detected_norm):
    if not expected_norm or not detected_norm:
        return False
    if len(detected_norm) < NAME_TRUNCATE_MIN_LEN:
        return False
    if expected_norm.startswith(detected_norm):
        ratio = len(detected_norm) / len(expected_norm)
        return ratio >= NAME_TRUNCATE_RATIO
    if detected_norm.startswith(expected_norm):
        ratio = len(expected_norm) / len(detected_norm)
        return ratio >= NAME_TRUNCATE_RATIO
    return False


def _check_date_field(field, expected, detected, conf, bboxes, discrepancies, date_diffs):
    exp_date = parse_date(expected)
    det_date = parse_date(detected)
    if exp_date is None or det_date is None:
        discrepancies.append(
            build_discrepancy(
                field,
                "warning",
                expected,
                detected,
                conf or 0.6,
                "Date missing or unparseable",
                bboxes.get(field),
            )
        )
        return
    diff = abs((exp_date - det_date).days)
    date_diffs[field] = diff
    if diff <= DATE_PASS_DAYS:
        return
    if diff <= DATE_WARN_DAYS:
        discrepancies.append(
            build_discrepancy(
                field,
                "warning",
                expected,
                detected,
                conf or 0.6,
                "Date off by a few days",
                bboxes.get(field),
            )
        )
        return
    discrepancies.append(
        build_discrepancy(
            field,
            "critical",
            expected,
            detected,
            conf or 0.6,
            "Date mismatch",
            bboxes.get(field),
        )
    )


def _check_amount_field(field, expected, detected, conf, bboxes, discrepancies, amount_diffs):
    exp_amt = parse_amount(expected)
    det_amt = parse_amount(detected)
    if exp_amt is None or det_amt is None:
        discrepancies.append(
            build_discrepancy(
                field,
                "warning",
                expected,
                detected,
                conf or 0.6,
                "Amount missing or unparseable",
                bboxes.get(field),
            )
        )
        return
    diff = abs(exp_amt - det_amt)
    rel = diff / exp_amt if exp_amt else diff
    amount_diffs[field] = {"abs": diff, "rel": rel}
    if diff <= AMOUNT_ABS_PASS or rel <= AMOUNT_REL_PASS:
        return
    if diff <= AMOUNT_ABS_WARN or rel <= AMOUNT_REL_WARN:
        discrepancies.append(
            build_discrepancy(
                field,
                "warning",
                expected,
                detected,
                conf or 0.7,
                "Amount slightly off",
                bboxes.get(field),
            )
        )
        return
    discrepancies.append(
        build_discrepancy(
            field,
            "critical",
            expected,
            detected,
            conf or 0.7,
            "Amount mismatch",
            bboxes.get(field),
        )
    )


def _decide_status(discrepancies, confidence_score):
    has_critical = any(d.get("issue_type") == "critical" for d in discrepancies)
    has_warning = any(d.get("issue_type") == "warning" for d in discrepancies)

    if has_critical:
        return STATUS_ON_CRITICAL
    if has_warning or confidence_score < CONFIDENCE_REVIEW_THRESHOLD:
        return "needs_review"
    return "approved"
