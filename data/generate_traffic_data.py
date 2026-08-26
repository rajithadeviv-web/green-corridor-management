"""
generate_traffic_data.py
-------------------------
Generates a SYNTHETIC / DEMO traffic dataset for the Green Corridor prototype.

IMPORTANT: This is prototype/demo data, not real government or real-time
traffic data. It is built using realistic statistical rules (rush hour
patterns, weather effects, weekday/weekend patterns) so that a machine
learning model trained on it produces sensible, explainable behaviour
during the SIH demo.

Run:
    python generate_traffic_data.py

Output:
    traffic_data.csv  (in the same folder)
"""

import numpy as np
import pandas as pd

RANDOM_SEED = 42
N_ROWS = 6000

np.random.seed(RANDOM_SEED)

WEATHER_OPTIONS = ["clear", "rain", "fog", "storm"]
WEATHER_WEIGHTS = [0.65, 0.20, 0.10, 0.05]


def is_rush_hour(hour: int) -> bool:
    return (7 <= hour <= 10) or (17 <= hour <= 20)


def generate_row(row_id: int) -> dict:
    hour = np.random.randint(0, 24)
    day_of_week = np.random.randint(0, 7)  # 0 = Monday ... 6 = Sunday
    weather = np.random.choice(WEATHER_OPTIONS, p=WEATHER_WEIGHTS)
    road_capacity = np.random.randint(800, 3000)  # vehicles/hour design capacity
    road_length = round(np.random.uniform(0.5, 8.0), 2)  # km

    # Base vehicle count depends on rush hour + weekend effect
    base_count = np.random.normal(loc=road_capacity * 0.35, scale=road_capacity * 0.12)

    if is_rush_hour(hour):
        base_count *= np.random.uniform(1.4, 1.9)

    if day_of_week >= 5:  # weekend -> generally lighter, except late morning
        base_count *= np.random.uniform(0.55, 0.85)

    weather_multiplier = {
        "clear": 1.0,
        "rain": 1.15,
        "fog": 1.05,
        "storm": 1.25,
    }[weather]
    base_count *= weather_multiplier

    vehicle_count = int(np.clip(base_count, 20, road_capacity * 1.6))

    # Traffic density: vehicles per km (rough approximation using road_length)
    traffic_density = round(vehicle_count / max(road_length, 0.1), 2)

    # Average speed decreases as density approaches/exceeds capacity
    capacity_ratio = vehicle_count / road_capacity
    base_speed = 60 - (capacity_ratio * 40)
    weather_speed_penalty = {
        "clear": 0,
        "rain": 6,
        "fog": 10,
        "storm": 15,
    }[weather]
    average_speed = np.clip(
        base_speed - weather_speed_penalty + np.random.normal(0, 3), 4, 65
    )
    average_speed = round(average_speed, 1)

    # Congestion score (0-100) derived from capacity ratio + speed drop
    congestion_score = np.clip(
        (capacity_ratio * 70) + ((60 - average_speed) / 60 * 30) + np.random.normal(0, 4),
        0,
        100,
    )

    if congestion_score < 25:
        congestion_level = "low"
    elif congestion_score < 50:
        congestion_level = "medium"
    elif congestion_score < 75:
        congestion_level = "high"
    else:
        congestion_level = "severe"

    return {
        "row_id": row_id,
        "vehicle_count": vehicle_count,
        "traffic_density": traffic_density,
        "average_speed": average_speed,
        "road_length": road_length,
        "hour": hour,
        "day_of_week": day_of_week,
        "weather": weather,
        "road_capacity": road_capacity,
        "congestion_score": round(congestion_score, 2),
        "congestion_level": congestion_level,
    }


def main():
    rows = [generate_row(i) for i in range(N_ROWS)]
    df = pd.DataFrame(rows)
    out_path = "traffic_data.csv"
    df.to_csv(out_path, index=False)
    print(f"[prototype/demo data] Generated {len(df)} rows -> {out_path}")
    print(df["congestion_level"].value_counts())


if __name__ == "__main__":
    main()
