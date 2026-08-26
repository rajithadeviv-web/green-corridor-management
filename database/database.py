"""
database.py
------------
SQLite connection and helper functions for the Green Corridor prototype.
Keeps all raw SQL in one place, separate from route/service logic.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "green_corridor.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they do not already exist."""
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Emergency requests
# ---------------------------------------------------------------------------

def create_emergency_request(vehicle_id, vehicle_type, source_node, destination_node,
                              emergency_level, priority_score):
    conn = get_connection()
    try:
        ts = now_iso()
        cur = conn.execute(
            """INSERT INTO emergency_requests
               (vehicle_id, vehicle_type, source_node, destination_node,
                emergency_level, priority_score, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (vehicle_id, vehicle_type, source_node, destination_node,
             emergency_level, priority_score, ts, ts),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_request_status(request_id, status, **kwargs):
    conn = get_connection()
    try:
        fields = ["status = ?", "updated_at = ?"]
        values = [status, now_iso()]
        for key in ("route_id", "eta_minutes", "distance_km"):
            if key in kwargs:
                fields.append(f"{key} = ?")
                values.append(kwargs[key])
        values.append(request_id)
        conn.execute(
            f"UPDATE emergency_requests SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def get_request(request_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM emergency_requests WHERE id = ?", (request_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_active_requests():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM emergency_requests "
            "WHERE status NOT IN ('completed', 'cancelled') "
            "ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def has_active_duplicate(vehicle_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM emergency_requests "
            "WHERE vehicle_id = ? AND status NOT IN ('completed', 'cancelled')",
            (vehicle_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Traffic records
# ---------------------------------------------------------------------------

def save_traffic_record(request_id, features: dict, predicted_congestion, congestion_score):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO traffic_records
               (request_id, vehicle_count, traffic_density, average_speed, road_length,
                hour, day_of_week, weather, road_capacity, predicted_congestion,
                congestion_score, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request_id,
                features.get("vehicle_count"),
                features.get("traffic_density"),
                features.get("average_speed"),
                features.get("road_length"),
                features.get("hour"),
                features.get("day_of_week"),
                features.get("weather"),
                features.get("road_capacity"),
                predicted_congestion,
                congestion_score,
                now_iso(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def save_routes(request_id, routes: list, selected_index: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM routes WHERE request_id = ?", (request_id,))
        for i, route in enumerate(routes):
            conn.execute(
                """INSERT INTO routes (request_id, route_json, is_selected, total_score, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (request_id, json.dumps(route), 1 if i == selected_index else 0,
                 route.get("total_score"), now_iso()),
            )
        conn.commit()
    finally:
        conn.close()


def get_routes(request_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM routes WHERE request_id = ? ORDER BY total_score ASC",
            (request_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["route"] = json.loads(d["route_json"])
            result.append(d)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Signal states
# ---------------------------------------------------------------------------

def upsert_signal_state(request_id, junction_id, state, is_priority):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM signal_states WHERE request_id = ? AND junction_id = ?",
            (request_id, junction_id),
        ).fetchone()
        ts = now_iso()
        if existing:
            conn.execute(
                "UPDATE signal_states SET state = ?, is_priority = ?, updated_at = ? WHERE id = ?",
                (state, int(is_priority), ts, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO signal_states (request_id, junction_id, state, is_priority, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (request_id, junction_id, state, int(is_priority), ts),
            )
        conn.commit()
    finally:
        conn.close()


def get_signal_states(request_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM signal_states WHERE request_id = ?", (request_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Traffic events
# ---------------------------------------------------------------------------

def save_traffic_event(request_id, event_type, location_node, description):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO traffic_events (request_id, event_type, location_node, description, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (request_id, event_type, location_node, description, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Completed trips
# ---------------------------------------------------------------------------

def save_completed_trip(request_id, vehicle_id, total_time_min, time_saved_min):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO completed_trips
               (request_id, vehicle_id, total_time_min, estimated_time_saved_min, completed_at)
               VALUES (?, ?, ?, ?, ?)""",
            (request_id, vehicle_id, total_time_min, time_saved_min, now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def get_dashboard_stats():
    conn = get_connection()
    try:
        active_vehicles = conn.execute(
            "SELECT COUNT(*) c FROM emergency_requests WHERE status NOT IN ('completed', 'cancelled')"
        ).fetchone()["c"]

        active_corridors = conn.execute(
            "SELECT COUNT(*) c FROM emergency_requests WHERE status = 'corridor_active'"
        ).fetchone()["c"]

        completed = conn.execute(
            "SELECT COUNT(*) c FROM completed_trips"
        ).fetchone()["c"]

        avg_time_saved = conn.execute(
            "SELECT AVG(estimated_time_saved_min) a FROM completed_trips"
        ).fetchone()["a"]

        signals_prioritized = conn.execute(
            "SELECT COUNT(*) c FROM signal_states WHERE is_priority = 1"
        ).fetchone()["c"]

        return {
            "active_vehicles": active_vehicles,
            "active_corridors": active_corridors,
            "completed_trips": completed,
            "avg_time_saved_min": round(avg_time_saved, 1) if avg_time_saved else 0,
            "signals_prioritized": signals_prioritized,
        }
    finally:
        conn.close()
