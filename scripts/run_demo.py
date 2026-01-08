from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.io.loader import load_all, ground_truth_map
from src.ml.train import load_model
from src.rules.validation import validate_invoice


def main(data_dir="data", model_path="models/logreg.pkl"):
    ground_truth, ocr_results, database = load_all(data_dir)
    gt_map = ground_truth_map(ground_truth)

    model_bundle = None
    model_file = Path(model_path)
    if model_file.exists():
        model_bundle = load_model(model_file)

    for inv_id, ocr_data in ocr_results.items():
        gt = gt_map.get(inv_id)
        if not gt:
            print(f"[SKIP] Missing ground truth for {inv_id}")
            continue
        result = validate_invoice(ocr_data, gt, database, model_bundle)
        print("=" * 60)
        print(f"Invoice: {inv_id}")
        print(f"Status: {result['status']}")
        print(f"Confidence: {result['confidence_score']:.3f}")
        print(f"Discrepancies: {len(result['discrepancies'])}")
        for d in result["discrepancies"]:
            field = d.get("field")
            issue = d.get("issue_type")
            expected = d.get("expected")
            detected = d.get("detected")
            print(f"- {field} [{issue}] expected={expected} detected={detected}")
    print("=" * 60)


if __name__ == "__main__":
    main()
