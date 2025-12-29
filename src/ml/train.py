import pickle

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

from src.ml.features import build_training_rows


def train_model(ground_truth, ocr_results):
    rows = build_training_rows(ground_truth, ocr_results)
    if not rows:
        return None

    features = [r[0] for r in rows]
    labels = [r[1] for r in rows]

    if len(set(labels)) < 2:
        return None

    vectorizer = DictVectorizer(sparse=False)
    X = vectorizer.fit_transform(features)

    model = LogisticRegression(max_iter=200, class_weight="balanced")
    model.fit(X, labels)

    return {
        "model": model,
        "vectorizer": vectorizer,
    }


def save_model(bundle, path):
    with open(path, "wb") as f:
        pickle.dump(bundle, f)


def load_model(path):
    with open(path, "rb") as f:
        return pickle.load(f)
