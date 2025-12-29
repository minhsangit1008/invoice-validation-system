from src.config import FIELD_WEIGHTS, SEVERITY_PENALTY


def compute_overall_confidence(ocr_confidence, discrepancies, p_wrong_by_field=None):
    p_wrong_by_field = p_wrong_by_field or {}
    weighted = 0.0
    weight_sum = 0.0
    field_scores = {}

    for field, weight in FIELD_WEIGHTS.items():
        ocr_conf = ocr_confidence.get(field)
        if field in p_wrong_by_field:
            p_wrong = p_wrong_by_field[field]
        elif ocr_conf is not None:
            p_wrong = max(0.0, min(1.0, 1.0 - float(ocr_conf)))
        else:
            p_wrong = 0.5
        score = 1.0 - p_wrong
        weighted += score * weight
        weight_sum += weight
        field_scores[field] = score

    base_score = weighted / weight_sum if weight_sum else 0.0

    penalty = 0.0
    for d in discrepancies:
        sev = d.get("issue_type")
        penalty += SEVERITY_PENALTY.get(sev, 0.0)

    penalty = min(penalty, 0.9)
    overall = max(0.0, min(1.0, base_score * (1.0 - penalty)))

    return overall, field_scores, base_score, penalty
