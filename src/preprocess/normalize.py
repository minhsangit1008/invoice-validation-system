import re
from datetime import datetime
from dateutil import parser as date_parser

from src.config import ADDRESS_ABBREV_MAP, COMPANY_SUFFIX_MAP, CONFUSABLE_MAP


_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def collapse_whitespace(text):
    return _WS_RE.sub(" ", text).strip()


def normalize_text(text):
    if text is None:
        return ""
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = collapse_whitespace(text)
    return text


def normalize_company_suffix(text):
    text = normalize_text(text)
    parts = text.split()
    if not parts:
        return text
    last = parts[-1]
    if last in COMPANY_SUFFIX_MAP:
        parts[-1] = COMPANY_SUFFIX_MAP[last]
    return " ".join(parts)


def normalize_address(text):
    text = normalize_text(text)
    parts = []
    for token in text.split():
        parts.append(ADDRESS_ABBREV_MAP.get(token, token))
    return " ".join(parts)


def ocr_confusion_normalize(text):
    if text is None:
        return ""
    out = []
    for ch in str(text):
        out.append(CONFUSABLE_MAP.get(ch, ch))
    return "".join(out)


def parse_amount(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    text = text.replace(",", "")
    text = re.sub(r"[^0-9.\-]", "", text)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    try:
        return date_parser.parse(str(value), dayfirst=False).date()
    except (ValueError, TypeError):
        return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
