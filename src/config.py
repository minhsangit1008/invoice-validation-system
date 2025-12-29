FUZZY_PASS = 0.90
FUZZY_WARN = 0.80

ADDRESS_FUZZY_PASS = 0.85
ADDRESS_FUZZY_WARN = 0.75

DATE_PASS_DAYS = 1
DATE_WARN_DAYS = 3

AMOUNT_ABS_PASS = 1.00
AMOUNT_ABS_WARN = 2.00
AMOUNT_REL_PASS = 0.005
AMOUNT_REL_WARN = 0.01

CONFUSABLE_MAP = {
    "0": "O",
    "O": "O",
    "1": "I",
    "I": "I",
    "L": "I",
    "l": "I",
    "5": "S",
    "S": "S",
    "8": "B",
    "B": "B",
}

ADDRESS_ABBREV_MAP = {
    "drive": "dr",
    "dr.": "dr",
    "street": "st",
    "st.": "st",
    "avenue": "ave",
    "ave.": "ave",
    "road": "rd",
    "rd.": "rd",
    "boulevard": "blvd",
    "blvd.": "blvd",
    "lane": "ln",
    "ln.": "ln",
    "suite": "ste",
    "ste.": "ste",
}

COMPANY_SUFFIX_MAP = {
    "inc": "inc",
    "inc.": "inc",
    "incorporated": "inc",
    "llc": "llc",
    "l.l.c.": "llc",
    "ltd": "ltd",
    "ltd.": "ltd",
    "co": "co",
    "co.": "co",
    "company": "co",
}

FIELD_WEIGHTS = {
    "po_number": 0.25,
    "vendor_name": 0.20,
    "total_amount": 0.20,
    "tax_amount": 0.10,
    "invoice_date": 0.05,
    "due_date": 0.05,
    "customer_name": 0.05,
    "vendor_address": 0.05,
    "customer_address": 0.05,
}

SEVERITY_PENALTY = {
    "critical": 0.50,
    "warning": 0.20,
    "informational": 0.05,
}

CONFIDENCE_REVIEW_THRESHOLD = 0.75
STATUS_ON_CRITICAL = "needs_review"

NAME_TRUNCATE_RATIO = 0.50
NAME_TRUNCATE_MIN_LEN = 4
