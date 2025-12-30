from pathlib import Path
import json
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.io.loader import load_all, ground_truth_map
from src.ml.train import load_model
from src.output.visualize import generate_visual_feedback
from src.rules.validation import validate_invoice


def main(data_dir="data", model_path="models/logreg.pkl", out_dir="sample_outputs"):
    ground_truth, ocr_results, database = load_all(data_dir)
    gt_map = ground_truth_map(ground_truth)

    model_bundle = None
    model_file = Path(model_path)
    if model_file.exists():
        model_bundle = load_model(model_file)

    out_path = Path(out_dir)
    out_path.mkdir(exist_ok=True)

    for inv_id, ocr_data in ocr_results.items():
        gt = gt_map.get(inv_id)
        if not gt:
            continue
        result = validate_invoice(ocr_data, gt, database, model_bundle)
        visual = generate_visual_feedback(result["discrepancies"])

        payload = {
            "invoice_id": inv_id,
            "status": result["status"],
            "confidence_score": result["confidence_score"],
            "discrepancies": result["discrepancies"],
            "visualization": visual,
        }

        output_file = out_path / f"{inv_id}.json"
        output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote outputs to {out_path}")


if __name__ == "__main__":
    main()
