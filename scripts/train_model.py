from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.io.loader import load_all
from src.ml.features import build_training_rows
from src.ml.train import save_model, train_model


def main(data_dir="data", model_path="models/logreg.pkl"):
    ground_truth, ocr_results, _ = load_all(data_dir)
    rows = build_training_rows(ground_truth, ocr_results)
    bundle = train_model(ground_truth, ocr_results)
    if not bundle:
        print("Not enough data to train model (need both classes).")
        return
    Path(model_path).parent.mkdir(exist_ok=True)
    save_model(bundle, model_path)
    print(f"Trained on {len(rows)} rows. Saved model to {model_path}.")


if __name__ == "__main__":
    main()
