def generate_visual_feedback(discrepancies):
    boxes = []
    for d in discrepancies:
        box = d.get("bounding_box")
        if box:
            boxes.append(
                {
                    "bounding_box": box,
                    "label": d.get("field"),
                    "severity": d.get("issue_type"),
                }
            )
    return boxes
