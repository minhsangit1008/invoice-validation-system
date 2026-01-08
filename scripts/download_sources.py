import csv
import ssl
import urllib.request
from pathlib import Path

from pypdf import PdfReader

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
SOURCES_PATH = DATA_DIR / "sources.csv"
RAW_PDFS_DIR = DATA_DIR / "raw_pdfs"
AUDIT_PATH = DATA_DIR / "sources_audit.csv"


def _download(url, dest, timeout=120):
    dest.parent.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def _audit_pdf(path):
    try:
        reader = PdfReader(str(path))
    except Exception:
        return 0, 0
    pages = len(reader.pages)
    text = []
    for page in reader.pages:
        text.append(page.extract_text() or "")
    text_len = len("".join(text).strip())
    return pages, text_len


def main():
    if not SOURCES_PATH.exists():
        raise FileNotFoundError(f"Missing {SOURCES_PATH}")

    rows = []
    with SOURCES_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    audit_rows = []
    for row in rows:
        invoice_id = row["invoice_id"].strip()
        url = row["url"].strip()
        pdf_path = RAW_PDFS_DIR / f"{invoice_id}.pdf"
        download_ok = True
        error = ""
        if not pdf_path.exists():
            print(f"[download] {invoice_id} -> {pdf_path.name}")
            try:
                _download(url, pdf_path)
            except Exception as exc:
                download_ok = False
                error = str(exc)
                print(f"[error] {invoice_id} download failed: {error}")
        else:
            print(f"[skip] {invoice_id} already exists")

        is_pdf = False
        pages = 0
        text_len = 0
        if pdf_path.exists():
            header = pdf_path.read_bytes()[:4]
            is_pdf = header == b"%PDF"
            if is_pdf:
                pages, text_len = _audit_pdf(pdf_path)
        audit_rows.append(
            {
                **row,
                "pages": pages,
                "text_len": text_len,
                "is_pdf": is_pdf,
                "download_ok": download_ok,
                "error": error,
                "local_path": str(pdf_path.relative_to(ROOT_DIR)),
            }
        )

    with AUDIT_PATH.open("w", encoding="utf-8", newline="") as f:
        fieldnames = list(audit_rows[0].keys()) if audit_rows else []
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_rows)

    print(f"[done] audit -> {AUDIT_PATH}")


if __name__ == "__main__":
    main()
