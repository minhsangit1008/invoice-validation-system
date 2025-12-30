import re
from datetime import date, datetime
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
    text = str(value).strip()
    if text == "":
        return None
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = text.replace(" ", "")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if text in ("", "-", ".", ","):
        return None

    if text.startswith("-"):
        negative = True
        text = text[1:]

    if "," in text and "." in text:
        last_comma = text.rfind(",")
        last_dot = text.rfind(".")
        if last_comma > last_dot:
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if re.search(r",\d{2}$", text):
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "." in text:
        if text.count(".") > 1:
            text = text.replace(".", "")
        elif re.search(r"\.\d{2}$", text):
            pass
        elif re.search(r"\.\d{3}$", text) and len(text.split(".")[0]) <= 3:
            text = text.replace(".", "")
    try:
        val = float(text)
        return -val if negative else val
    except ValueError:
        return None


def parse_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if text == "":
        return None

    if re.fullmatch(r"\d{8}", text):
        year = int(text[:4])
        if year >= 1900:
            try:
                return datetime.strptime(text, "%Y%m%d").date()
            except ValueError:
                pass
        try:
            return datetime.strptime(text, "%d%m%Y").date()
        except ValueError:
            return None

    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d.%m.%Y",
        "%Y.%m.%d",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    for dayfirst in (False, True):
        try:
            return date_parser.parse(
                text, dayfirst=dayfirst, yearfirst=True, fuzzy=True
            ).date()
        except (ValueError, TypeError):
            continue
    return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
