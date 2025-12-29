from src.ml.features import extract_features


def predict_p_wrong(bundle, field, expected, detected, ocr_conf):
    if not bundle:
        return _fallback(ocr_conf)
    model = bundle.get("model")
    vectorizer = bundle.get("vectorizer")
    if model is None or vectorizer is None:
        return _fallback(ocr_conf)

    features = extract_features(field, expected, detected, ocr_conf)
    X = vectorizer.transform([features])
    proba = model.predict_proba(X)[0]
    return float(proba[1])


def _fallback(ocr_conf):
    if ocr_conf is None:
        return 0.5
    return max(0.0, min(1.0, 1.0 - float(ocr_conf)))
