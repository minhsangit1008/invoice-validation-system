def build_discrepancy(
    field,
    issue_type,
    expected,
    detected,
    confidence,
    suggestion=None,
    bounding_box=None,
):
    return {
        "field": field,
        "issue_type": issue_type,
        "expected": expected,
        "detected": detected,
        "confidence": float(confidence) if confidence is not None else None,
        "suggestion": suggestion,
        "bounding_box": bounding_box,
    }
