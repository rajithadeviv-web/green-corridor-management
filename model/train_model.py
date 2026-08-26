"""
train_model.py
----------------
Trains a RandomForestClassifier to predict traffic congestion level
from the synthetic prototype dataset (data/traffic_data.csv).

Pipeline:
    1. Load data
    2. Preprocess (encode categorical weather column)
    3. Train/test split
    4. Train RandomForestClassifier
    5. Evaluate (accuracy, precision, recall, f1, confusion matrix)
    6. Save model + encoder + metrics to disk

Run:
    python train_model.py

Outputs (in this folder):
    traffic_model.pkl     - trained RandomForest model
    weather_encoder.pkl   - LabelEncoder for the 'weather' column
    model_metrics.json    - evaluation metrics for display in the dashboard
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "traffic_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "traffic_model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "weather_encoder.pkl")
METRICS_PATH = os.path.join(BASE_DIR, "model_metrics.json")

FEATURE_COLUMNS = [
    "vehicle_count",
    "traffic_density",
    "average_speed",
    "road_length",
    "hour",
    "day_of_week",
    "weather_encoded",
    "road_capacity",
]
TARGET_COLUMN = "congestion_level"
CLASS_ORDER = ["low", "medium", "high", "severe"]


def main():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(
            f"Dataset not found at {DATA_PATH}. "
            "Run data/generate_traffic_data.py first."
        )

    df = pd.read_csv(DATA_PATH)

    # --- Preprocessing ---
    weather_encoder = LabelEncoder()
    df["weather_encoded"] = weather_encoder.fit_transform(df["weather"])

    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    # --- Train/test split ---
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # --- Model training ---
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        class_weight="balanced",
    )
    model.fit(X_train, y_train)

    # --- Evaluation ---
    y_pred = model.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, average="macro", zero_division=0)
    recall = recall_score(y_test, y_pred, average="macro", zero_division=0)
    f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=CLASS_ORDER)

    feature_importances = dict(
        zip(FEATURE_COLUMNS, [round(float(v), 4) for v in model.feature_importances_])
    )

    metrics = {
        "model_type": "RandomForestClassifier",
        "n_estimators": 200,
        "trained_on": "synthetic/demo prototype dataset (data/traffic_data.csv)",
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "accuracy": round(float(accuracy), 4),
        "precision_macro": round(float(precision), 4),
        "recall_macro": round(float(recall), 4),
        "f1_macro": round(float(f1), 4),
        "confusion_matrix": {
            "labels": CLASS_ORDER,
            "matrix": cm.tolist(),
        },
        "feature_importances": feature_importances,
        "feature_order": FEATURE_COLUMNS,
        "class_order": CLASS_ORDER,
    }

    # --- Save artifacts ---
    joblib.dump(model, MODEL_PATH)
    joblib.dump(weather_encoder, ENCODER_PATH)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print("Training complete.")
    print(f"Accuracy: {accuracy:.4f} | Precision: {precision:.4f} | "
          f"Recall: {recall:.4f} | F1: {f1:.4f}")
    print(f"Model saved to:   {MODEL_PATH}")
    print(f"Encoder saved to: {ENCODER_PATH}")
    print(f"Metrics saved to: {METRICS_PATH}")


if __name__ == "__main__":
    main()
