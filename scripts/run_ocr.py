from pathlib import Path
import json
import os
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PIL import Image, ImageFilter, ImageOps
import pytesseract

from src.config import (
    OCR_DPI,
    OCR_LANGS,
    OCR_RAW_PATH,
    RAW_PDF_DIR,
    RENDERED_DIR,
    SIMULATE_SCAN_IDS,
    TESSDATA_DIR,
    TESSERACT_CMD,
)
from src.ocr.render import render_pdf_to_images


def _configure_tesseract():
    if TESSERACT_CMD and Path(TESSERACT_CMD).exists():
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_CMD)
    if TESSDATA_DIR and Path(TESSDATA_DIR).exists():
        os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)


def _resolve_langs():
    langs = OCR_LANGS
    if "vie" in OCR_LANGS:
        tess_vie = (TESSDATA_DIR / "vie.traineddata") if TESSDATA_DIR else None
        if not tess_vie or not tess_vie.exists():
            langs = "eng"
    return langs


def _tess_config():
    return f"--oem 3 --psm 6 -c preserve_interword_spaces=1 --dpi {OCR_DPI}"


def _preprocess_image(img):
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    denoised = gray.filter(ImageFilter.MedianFilter(size=3))
    bw = denoised.point(lambda p: 0 if p < 160 else 255)
    return bw


def _ocr_image(image_path):
    img = _preprocess_image(Image.open(image_path))
    config = _tess_config()
    data = pytesseract.image_to_data(
        img,
        lang=_resolve_langs(),
        output_type=pytesseract.Output.DICT,
        config=config,
    )
    tokens = []
    line_buckets = {}
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf = float(data["conf"][i]) if data["conf"][i] != "-1" else None
        left = int(data["left"][i])
        top = int(data["top"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])
        token = {
            "text": text,
            "conf": conf,
            "x1": left,
            "y1": top,
            "x2": left + width,
            "y2": top + height,
            "line_num": int(data["line_num"][i]),
            "block_num": int(data["block_num"][i]),
            "par_num": int(data["par_num"][i]),
            "word_num": int(data["word_num"][i]),
        }
        tokens.append(token)
        line_key = (token["block_num"], token["par_num"], token["line_num"])
        line_buckets.setdefault(line_key, []).append(token)

    lines = []
    for line_key, items in line_buckets.items():
        items = sorted(items, key=lambda t: t["x1"])
        text = " ".join(t["text"] for t in items)
        x1 = min(t["x1"] for t in items)
        y1 = min(t["y1"] for t in items)
        x2 = max(t["x2"] for t in items)
        y2 = max(t["y2"] for t in items)
        confs = [t["conf"] for t in items if t["conf"] is not None]
        avg_conf = sum(confs) / len(confs) if confs else None
        lines.append(
            {
                "text": text,
                "conf": avg_conf,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "line_key": line_key,
            }
        )
    lines = sorted(lines, key=lambda l: (l["y1"], l["x1"]))
    return tokens, lines, img.size


def main():
    _configure_tesseract()
    RAW_PDF_DIR.mkdir(parents=True, exist_ok=True)
    RENDERED_DIR.mkdir(parents=True, exist_ok=True)
    OCR_RAW_PATH.parent.mkdir(parents=True, exist_ok=True)

    ocr_raw = {}
    for pdf_path in sorted(RAW_PDF_DIR.glob("*.pdf")):
        invoice_id = pdf_path.stem
        simulate = invoice_id in SIMULATE_SCAN_IDS
        image_paths = render_pdf_to_images(
            pdf_path,
            RENDERED_DIR,
            dpi=OCR_DPI,
            simulate_scan=simulate,
        )
        pages = []
        all_text = []
        for image_path in image_paths:
            tokens, lines, size = _ocr_image(image_path)
            page_text = "\n".join(line["text"] for line in lines)
            all_text.append(page_text)
            pages.append(
                {
                    "image_path": str(Path(image_path).relative_to(OCR_RAW_PATH.parent.parent)),
                    "width": size[0],
                    "height": size[1],
                    "tokens": tokens,
                    "lines": lines,
                }
            )
        ocr_raw[invoice_id] = {
            "raw_text": "\n".join(all_text),
            "pages": pages,
        }

    OCR_RAW_PATH.write_text(json.dumps(ocr_raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {OCR_RAW_PATH}")


if __name__ == "__main__":
    main()
