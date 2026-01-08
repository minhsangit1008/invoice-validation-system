from pathlib import Path

import fitz
import numpy as np
from PIL import Image, ImageFilter, ImageOps


def render_pdf_to_images(pdf_path, output_dir, dpi=300, simulate_scan=False, scan_config=None):
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    image_paths = []
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        if simulate_scan:
            img = _simulate_scan(img, scan_config or {})
        out_path = output_dir / f"{pdf_path.stem}_p{page_index + 1}.png"
        img.save(out_path)
        image_paths.append(out_path)
    return image_paths


def _simulate_scan(img, scan_config):
    rotation = scan_config.get("rotation", 0.8)
    blur_radius = scan_config.get("blur_radius", 0.4)
    noise_sigma = scan_config.get("noise_sigma", 8.0)

    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    if rotation:
        gray = gray.rotate(rotation, expand=True, fillcolor=255)
    if blur_radius:
        gray = gray.filter(ImageFilter.GaussianBlur(blur_radius))

    arr = np.array(gray).astype(np.float32)
    if noise_sigma:
        noise = np.random.normal(0, noise_sigma, arr.shape)
        arr = np.clip(arr + noise, 0, 255)
    noisy = Image.fromarray(arr.astype(np.uint8), mode="L")
    return noisy.convert("RGB")
