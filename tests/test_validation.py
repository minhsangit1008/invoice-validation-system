from src.rules.validation import validate_invoice


def make_base_case():
    expected = {
        "vendor_name": "Acme Data Services LLC",
        "vendor_address": "900 Market Street, San Jose, CA 95113",
        "customer_name": "Suri Technologies",
        "customer_address": "456 Data Street, Austin, TX 78701",
        "po_number": "PO-45678",
        "invoice_date": "2024-02-02",
        "due_date": "2024-03-03",
        "subtotal": 100.00,
        "tax_amount": 9.00,
        "total_amount": 109.00,
        "line_items": [
            {
                "description": "Support Retainer",
                "quantity": 1,
                "unit_price": 100.00,
                "total": 100.00,
            }
        ],
    }

    ocr_data = {
        "structured_data": {
            "vendor_name": "Acme Data Services LLC",
            "vendor_address": "900 Market Street, San Jose, CA 95113",
            "customer_name": "Suri Technologies",
            "customer_address": "456 Data Street, Austin, TX 78701",
            "po_number": "PO-45678",
            "invoice_date": "2024-02-02",
            "due_date": "2024-03-03",
            "subtotal": 100.00,
            "tax_amount": 9.00,
            "total_amount": 109.00,
            "line_items": [
                {
                    "text": "Support Retainer\nQty: 1\nPrice: $100.00\nTotal: $100.00"
                }
            ],
        },
        "confidence_scores": {
            "vendor_name": 0.95,
            "po_number": 0.90,
            "total_amount": 0.98,
        },
        "bounding_boxes": {},
    }

    database = {
        "purchase_orders": {
            "PO-45678": {
                "vendor": "Acme Data Services LLC",
                "approved_amount": 109.00,
                "valid_items": ["Support Retainer"],
                "max_quantity": {"Support Retainer": 3},
                "tax_rate": 0.09,
            }
        },
        "vendor_master": {},
        "customer_info": {},
    }

    ground_truth = {
        "invoice_id": "INV-TEST-001",
        "expected_data": expected,
    }

    return ground_truth, ocr_data, database


def find_discrepancy(result, field):
    for d in result["discrepancies"]:
        if d.get("field") == field:
            return d
    return None


def test_missing_field():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["vendor_name"] = ""
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "vendor_name")
    assert d is not None
    assert d["issue_type"] == "critical"


def test_ocr_confusion_po_number():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["po_number"] = "P0-45678"
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "po_number")
    assert d is not None
    assert d["issue_type"] == "warning"


def test_date_out_of_range():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["due_date"] = "2024-03-20"
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "due_date")
    assert d is not None
    assert d["issue_type"] == "critical"


def test_total_amount_mismatch():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["total_amount"] = 150.00
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "total_amount")
    assert d is not None
    assert d["issue_type"] == "critical"


def test_line_item_anomaly():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["line_items"] = [
        {"text": "Support Retainer\nQty: 5\nPrice: $100.00\nTotal: $500.00"}
    ]
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "line_items[0].quantity")
    assert d is not None
    assert d["issue_type"] == "critical"


def test_missing_address_warning():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["customer_address"] = ""
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "customer_address")
    assert d is not None
    assert d["issue_type"] == "warning"


def test_invalid_date_format_warning():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["invoice_date"] = "2024-13-40"
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "invoice_date")
    assert d is not None
    assert d["issue_type"] == "warning"


def test_tax_amount_warning():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["tax_amount"] = 10.50
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "tax_amount")
    assert d is not None
    assert d["issue_type"] == "warning"


def test_line_total_mismatch_warning():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["line_items"] = [
        {"text": "Support Retainer\nQty: 1\nPrice: $100.00\nTotal: $102.00"}
    ]
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "line_items[0].total")
    assert d is not None
    assert d["issue_type"] == "warning"


def test_address_abbreviation_no_discrepancy():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["vendor_address"] = "900 Market St, San Jose, CA 95113"
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "vendor_address")
    assert d is None


def test_name_truncated_warning():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["customer_name"] = "Suri Tech"
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "customer_name")
    assert d is not None
    assert d["issue_type"] == "warning"


def test_po_number_mismatch_critical():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["po_number"] = "PO-99999"
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "po_number")
    assert d is not None
    assert d["issue_type"] == "critical"


def test_date_within_warning_window():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["due_date"] = "2024-03-05"
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "due_date")
    assert d is not None
    assert d["issue_type"] == "warning"


def test_amount_within_tolerance_no_discrepancy():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["total_amount"] = 109.50
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "total_amount")
    assert d is None


def test_item_not_in_po_list_critical():
    gt, ocr, db = make_base_case()
    ocr["structured_data"]["line_items"] = [
        {"text": "Unknown Service\nQty: 1\nPrice: $100.00\nTotal: $100.00"}
    ]
    result = validate_invoice(ocr, gt, db, model_bundle=None)
    d = find_discrepancy(result, "line_items[0].description")
    assert d is not None
    assert d["issue_type"] == "critical"
