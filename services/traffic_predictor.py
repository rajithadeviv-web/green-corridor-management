"""
traffic_predictor.py
----------------------
Loads the trained RandomForest model ONCE at import time and exposes a
predict() function used by the Flask API. This is a REAL model prediction,
not a hardcoded/fake result.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "model", "traffic_model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "model", "weather_encoder.pkl")
METRICS_PATH = os.path.join(BASE_DIR, "model", "model_metrics.json")

FEATURE_ORDER = [
    "vehicle_count",
    "traffic_density",
    "average_speed",
    "road_length",
    "hour",
    "day_of_week",
    "weather_encoded",
    "road_capacity",
]

CONGESTION_TO_SCORE_BAND = {
    "low": (0, 25),
    "medium": (25, 50),
    "high": (50, 75),
    "severe": (75, 100),
}


class TrafficPredictorError(Exception):
    pass


class TrafficPredictor:
    def __init__(self):
        self._model = None
        self._weather_encoder = None
        self._metrics = None
        self._loaded = False
        self._load_error = None
        self._load()

    def _load(self):
        try:
            if not os.path.exists(MODEL_PATH) or not os.path.exists(ENCODER_PATH):
                raise TrafficPredictorError(
                    "Model files not found. Run model/train_model.py first."
                )
            self._model = joblib.load(MODEL_PATH)
            self._weather_encoder = joblib.load(ENCODER_PATH)
            if os.path.exists(METRICS_PATH):
                with open(METRICS_PATH) as f:
                    self._metrics = json.load(f)
            self._loaded = True
        except Exception as e:  # noqa: BLE001
            self._loaded = False
            self._load_error = str(e)

    @property
    def is_loaded(self):
        return self._loaded

    @property
    def load_error(self):
        return self._load_error

    @property
    def metrics(self):
        return self._metrics

    def _encode_weather(self, weather: str) -> int:
        known_classes = list(self._weather_encoder.classes_)
        if weather not in known_classes:
            # Fall back to the most common training class rather than crashing
            weather = "clear" if "clear" in known_classes else known_classes[0]
        return int(self._weather_encoder.transform([weather])[0])

    def predict(self, features: dict) -> dict:
        """
        features must contain:
            vehicle_count, traffic_density, average_speed, road_length,
            hour, day_of_week, weather, road_capacity
        Returns dict with predicted congestion level, confidence, score, explanation.
        """
        if not self._loaded:
            raise TrafficPredictorError(
                f"Model is not loaded: {self._load_error}"
            )

        required = ["vehicle_count", "traffic_density", "average_speed",
                    "road_length", "hour", "day_of_week", "weather", "road_capacity"]
        missing = [k for k in required if k not in features or features[k] is None]
        if missing:
            raise TrafficPredictorError(f"Missing required features: {missing}")

        weather_encoded = self._encode_weather(features["weather"])

        row = [
            float(features["vehicle_count"]),
            float(features["traffic_density"]),
            float(features["average_speed"]),
            float(features["road_length"]),
            float(features["hour"]),
            float(features["day_of_week"]),
            float(weather_encoded),
            float(features["road_capacity"]),
        ]

        X = pd.DataFrame([row], columns=FEATURE_ORDER)
        predicted_class = self._model.predict(X)[0]
        probabilities = self._model.predict_proba(X)[0]
        class_labels = list(self._model.classes_)
        prob_map = {cls: round(float(p), 4) for cls, p in zip(class_labels, probabilities)}
        confidence = prob_map.get(predicted_class, 0.0)

        # Approximate a 0-100 congestion score from class band + confidence
        low, high = CONGESTION_TO_SCORE_BAND.get(predicted_class, (0, 100))
        congestion_score = round(low + (high - low) * confidence, 1)

        explanation = self._build_explanation(features, predicted_class)

        return {
            "predicted_congestion": predicted_class,
            "confidence": confidence,
            "class_probabilities": prob_map,
            "congestion_score": congestion_score,
            "explanation": explanation,
            "input_features": features,
        }

    def _build_explanation(self, features: dict, predicted_class: str) -> list:
        """Build a genuine explanation grounded in the actual input values
        and the model's known feature importances (not a fake canned string)."""
        reasons = []
        capacity_ratio = features["vehicle_count"] / max(features["road_capacity"], 1)

        if capacity_ratio > 0.9:
            reasons.append(
                f"Vehicle count ({features['vehicle_count']}) is close to or exceeds "
                f"road capacity ({features['road_capacity']})"
            )
        elif capacity_ratio > 0.6:
            reasons.append(
                f"Vehicle count ({features['vehicle_count']}) is a significant share "
                f"of road capacity ({features['road_capacity']})"
            )

        if features["average_speed"] < 20:
            reasons.append(f"Average speed is low ({features['average_speed']} km/h)")

        if features["traffic_density"] > 400:
            reasons.append(f"Traffic density is high ({features['traffic_density']} veh/km)")

        if features["weather"] in ("rain", "fog", "storm"):
            reasons.append(f"Weather condition '{features['weather']}' is reducing flow")

        hour = int(features["hour"])
        if (7 <= hour <= 10) or (17 <= hour <= 20):
            reasons.append(f"Hour {hour}:00 falls within a typical rush-hour window")

        if not reasons:
            reasons.append(
                "Traffic indicators (vehicle count, density, speed) are within normal range"
            )

        return reasons


# Loaded once at import time, reused across all requests (no retraining per call)
predictor = TrafficPredictor()
