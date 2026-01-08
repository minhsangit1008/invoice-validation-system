import urllib.request
from pathlib import Path
import sys
import shutil

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.config import TESSDATA_DIR


def main():
    TESSDATA_DIR.mkdir(parents=True, exist_ok=True)
    target = TESSDATA_DIR / "vie.traineddata"
    if not target.exists():
        url = "https://github.com/tesseract-ocr/tessdata/raw/main/vie.traineddata"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            target.write_bytes(resp.read())
        print(f"[done] {target}")
    else:
        print(f"[skip] {target} already exists")

    eng_src = Path(r"C:\\Program Files\\Tesseract-OCR\\tessdata\\eng.traineddata")
    eng_dest = TESSDATA_DIR / "eng.traineddata"
    if eng_src.exists() and not eng_dest.exists():
        shutil.copy(eng_src, eng_dest)
        print(f"[copy] {eng_dest}")


if __name__ == "__main__":
    main()
