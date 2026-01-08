from pathlib import Path

from PIL import Image, ImageDraw


def generate_visual_feedback(discrepancies):
    boxes = []
    placeholder_y = 20
    for idx, d in enumerate(discrepancies):
        box = d.get("bounding_box")
        if not box:
            box = _placeholder_box(idx, placeholder_y)
            placeholder_y += 24
        boxes.append(
            {
                "bounding_box": box,
                "label": d.get("field"),
                "severity": d.get("issue_type"),
            }
        )
    return boxes


def render_highlight_image(image_path, discrepancies, output_path):
    image_path = Path(image_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    img_w, img_h = img.size
    for d in discrepancies:
        box = d.get("bounding_box")
        if not box:
            continue
        if _is_box_too_large(box, img_w, img_h):
            continue
        color = _severity_color(d.get("issue_type"))
        x1, y1, x2, y2 = _box_to_tuple(box)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label = f"{d.get('field')} ({d.get('issue_type')})"
        draw.text((x1, max(0, y1 - 14)), label, fill=color)
    img.save(output_path)


def _box_to_tuple(box):
    return int(box["x1"]), int(box["y1"]), int(box["x2"]), int(box["y2"])


def _is_box_too_large(box, img_w, img_h):
    width = max(0, box["x2"] - box["x1"])
    height = max(0, box["y2"] - box["y1"])
    if img_w == 0 or img_h == 0:
        return True
    area_ratio = (width * height) / float(img_w * img_h)
    if area_ratio > 0.35:
        return True
    if width / img_w > 0.95 and height / img_h > 0.5:
        return True
    return False


def _severity_color(severity):
    if severity == "critical":
        return (220, 20, 60)
    if severity == "warning":
        return (255, 165, 0)
    return (70, 130, 180)


def _placeholder_box(idx, y):
    x1 = 10
    x2 = 260
    y1 = y + (idx * 2)
    y2 = y1 + 18
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
