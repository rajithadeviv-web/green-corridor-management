import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.traffic_predictor import predictor, TrafficPredictorError


class TestTrafficPredictor(unittest.TestCase):
    def test_model_loaded(self):
        self.assertTrue(predictor.is_loaded, f"Model failed to load: {predictor.load_error}")

    def test_predict_valid_input(self):
        features = {
            "vehicle_count": 1500,
            "traffic_density": 600,
            "average_speed": 15,
            "road_length": 2.5,
            "hour": 9,
            "day_of_week": 1,
            "weather": "clear",
            "road_capacity": 1800,
        }
        result = predictor.predict(features)
        self.assertIn(result["predicted_congestion"], ["low", "medium", "high", "severe"])
        self.assertGreaterEqual(result["confidence"], 0)
        self.assertLessEqual(result["confidence"], 1)
        self.assertTrue(len(result["explanation"]) > 0)

    def test_predict_low_traffic_leans_low_or_medium(self):
        features = {
            "vehicle_count": 100,
            "traffic_density": 40,
            "average_speed": 55,
            "road_length": 2.5,
            "hour": 3,
            "day_of_week": 2,
            "weather": "clear",
            "road_capacity": 2000,
        }
        result = predictor.predict(features)
        self.assertIn(result["predicted_congestion"], ["low", "medium"])

    def test_predict_missing_features_raises(self):
        with self.assertRaises(TrafficPredictorError):
            predictor.predict({"vehicle_count": 500})

    def test_predict_unknown_weather_falls_back(self):
        features = {
            "vehicle_count": 500,
            "traffic_density": 200,
            "average_speed": 40,
            "road_length": 2.0,
            "hour": 12,
            "day_of_week": 3,
            "weather": "unknown_weather_type",
            "road_capacity": 1500,
        }
        # should not raise, should fall back to a known class
        result = predictor.predict(features)
        self.assertIn(result["predicted_congestion"], ["low", "medium", "high", "severe"])


if __name__ == "__main__":
    unittest.main()
