try:
    from rapidfuzz import fuzz as _fuzz
except Exception:  # pragma: no cover
    _fuzz = None

from difflib import SequenceMatcher

from src.preprocess.normalize import normalize_text


def _ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()


def fuzzy_score(a, b, normalizer=normalize_text):
    if a is None or b is None:
        return 0.0, "none"
    a_norm = normalizer(a)
    b_norm = normalizer(b)
    if a_norm == "" and b_norm == "":
        return 1.0, "empty"
    if _fuzz is not None:
        token_score = _fuzz.token_set_ratio(a_norm, b_norm) / 100.0
        edit_score = _fuzz.ratio(a_norm, b_norm) / 100.0
    else:
        token_score = _token_set_ratio(a_norm, b_norm)
        edit_score = _ratio(a_norm, b_norm)
    if token_score >= edit_score:
        return token_score, "token_set"
    return edit_score, "edit_ratio"


def _token_set_ratio(a, b):
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens and not b_tokens:
        return 1.0
    intersect = " ".join(sorted(a_tokens & b_tokens))
    a_only = " ".join(sorted(a_tokens - b_tokens))
    b_only = " ".join(sorted(b_tokens - a_tokens))
    combo_a = " ".join([intersect, a_only]).strip()
    combo_b = " ".join([intersect, b_only]).strip()
    return max(_ratio(intersect, combo_a), _ratio(intersect, combo_b), _ratio(combo_a, combo_b))
