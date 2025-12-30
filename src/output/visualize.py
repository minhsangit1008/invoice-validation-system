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


def _placeholder_box(idx, y):
    x1 = 10
    x2 = 260
    y1 = y + (idx * 2)
    y2 = y1 + 18
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
