"""
app.py
-------
AI-Based Green Corridor Management for Emergency Vehicles
Flask REST API + dashboard entry point.

Run:
    python app.py

Then open:
    http://127.0.0.1:5000
"""

import json
import os
from datetime import datetime

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from database import database as db
from services.corridor_manager import corridor_manager, SIMULATION_MODE_LABEL
from services.emergency_manager import emergency_manager, EmergencyManagerError
from services.route_optimizer import route_optimizer, RouteOptimizerError, DEFAULT_WEIGHTS
from services.simulation_engine import simulation_engine
from services.traffic_predictor import predictor, TrafficPredictorError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
CORS(app)

# Initialize database (creates tables if they do not exist)
db.init_db()

TRAFFIC_EVENT_TYPES = {
    "accident", "road_blockage", "sudden_congestion", "traffic_increase", "road_closure"
}


def error_response(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code


def ok_response(data, status_code=200):
    return jsonify({"success": True, **data}), status_code


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", simulation_label=SIMULATION_MODE_LABEL)


# ---------------------------------------------------------------------------
# Emergency request endpoints
# ---------------------------------------------------------------------------

@app.route("/api/emergency/create", methods=["POST"])
def create_emergency():
    payload = request.get_json(silent=True) or {}
    try:
        request_id = emergency_manager.create_request(payload)
    except EmergencyManagerError as e:
        return error_response(str(e), 400)

    req = db.get_request(request_id)
    return ok_response({"request": req}, 201)


@app.route("/api/emergency/active", methods=["GET"])
def active_emergencies():
    return ok_response({"requests": db.get_active_requests()})


@app.route("/api/emergency/<int:request_id>", methods=["GET"])
def get_emergency(request_id):
    req = db.get_request(request_id)
    if not req:
        return error_response("Emergency request not found", 404)
    return ok_response({"request": req})


# ---------------------------------------------------------------------------
# Traffic prediction endpoint
# ---------------------------------------------------------------------------

@app.route("/api/traffic/predict", methods=["POST"])
def predict_traffic():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")

    features = {
        "vehicle_count": payload.get("vehicle_count"),
        "traffic_density": payload.get("traffic_density"),
        "average_speed": payload.get("average_speed"),
        "road_length": payload.get("road_length"),
        "hour": payload.get("hour", datetime.now().hour),
        "day_of_week": payload.get("day_of_week", datetime.now().weekday()),
        "weather": payload.get("weather", "clear"),
        "road_capacity": payload.get("road_capacity"),
    }

    try:
        result = predictor.predict(features)
    except TrafficPredictorError as e:
        return error_response(str(e), 400 if "Missing" in str(e) else 503)

    if request_id:
        db.save_traffic_record(
            request_id, features, result["predicted_congestion"], result["congestion_score"]
        )

    return ok_response({"prediction": result})


# ---------------------------------------------------------------------------
# Route calculation endpoint
# ---------------------------------------------------------------------------

@app.route("/api/routes/calculate", methods=["POST"])
def calculate_routes():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    source = payload.get("source")
    destination = payload.get("destination")
    congestion_hint = payload.get("congestion_level", "medium")
    weights = payload.get("weights") or DEFAULT_WEIGHTS

    if not source or not destination:
        return error_response("source and destination are required", 400)

    try:
        routes = route_optimizer.generate_routes(
            source, destination, congestion_level_hint=congestion_hint, weights=weights
        )
    except RouteOptimizerError as e:
        return error_response(str(e), 400)

    # attach human-readable labels
    for r in routes:
        r["junction_labels"] = [route_optimizer.node_label(j) for j in r["junctions"]]
        r["path_labels"] = [route_optimizer.node_label(n) for n in r["path_nodes"]]

    if request_id:
        selected_index = 0
        db.save_routes(request_id, routes, selected_index)
        best = routes[selected_index]
        db.update_request_status(
            request_id, "route_selected",
            eta_minutes=best["estimated_travel_time_min"],
            distance_km=best["distance_km"],
        )

    return ok_response({"routes": routes, "recommended": routes[0]})


@app.route("/api/routes/<int:request_id>", methods=["GET"])
def get_routes_for_request(request_id):
    routes = db.get_routes(request_id)
    return ok_response({"routes": routes})


# ---------------------------------------------------------------------------
# Corridor endpoints
# ---------------------------------------------------------------------------

@app.route("/api/corridor/activate", methods=["POST"])
def activate_corridor():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    junctions = payload.get("junctions", [])
    path_nodes = payload.get("path_nodes", [])
    distance_km = payload.get("distance_km", 0)
    estimated_travel_time_min = payload.get("estimated_travel_time_min", 0)

    if not request_id or not junctions:
        return error_response("request_id and junctions are required", 400)

    states = corridor_manager.activate_corridor(request_id, junctions)
    simulation_engine.start(request_id, {
        "path_nodes": path_nodes,
        "distance_km": distance_km,
    })

    return ok_response({
        "signal_states": states,
        "simulation_mode": SIMULATION_MODE_LABEL,
        "vehicle_state": simulation_engine.get_state(request_id),
    })


@app.route("/api/corridor/release", methods=["POST"])
def release_corridor():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    junctions = payload.get("junctions", [])

    if not request_id:
        return error_response("request_id is required", 400)

    corridor_manager.release_corridor(request_id, junctions)

    total_time = payload.get("total_time_min", 0)
    time_saved = payload.get("time_saved_min", 0)
    req = db.get_request(request_id)
    if req:
        db.save_completed_trip(request_id, req["vehicle_id"], total_time, time_saved)

    simulation_engine.reset(request_id)

    return ok_response({"message": "Corridor released, normal traffic resumed"})


@app.route("/api/corridor/status/<int:request_id>", methods=["GET"])
def corridor_status(request_id):
    states = corridor_manager.get_corridor_status(request_id)
    return ok_response({"signal_states": states, "simulation_mode": SIMULATION_MODE_LABEL})


@app.route("/api/corridor/recalculate", methods=["POST"])
def recalculate_corridor():
    """Re-run route optimization after a traffic event and re-activate corridor
    on the new best route."""
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    source = payload.get("source")
    destination = payload.get("destination")
    weights = payload.get("weights") or DEFAULT_WEIGHTS

    if not request_id or not source or not destination:
        return error_response("request_id, source and destination are required", 400)

    try:
        routes = route_optimizer.generate_routes(
            source, destination, congestion_level_hint="high", weights=weights
        )
    except RouteOptimizerError as e:
        return error_response(str(e), 400)

    for r in routes:
        r["junction_labels"] = [route_optimizer.node_label(j) for j in r["junctions"]]
        r["path_labels"] = [route_optimizer.node_label(n) for n in r["path_nodes"]]

    best = routes[0]
    db.save_routes(request_id, routes, 0)
    db.update_request_status(
        request_id, "corridor_active",
        eta_minutes=best["estimated_travel_time_min"],
        distance_km=best["distance_km"],
    )

    states = corridor_manager.activate_corridor(request_id, best["junctions"])
    simulation_engine.start(request_id, {
        "path_nodes": best["path_nodes"],
        "distance_km": best["distance_km"],
    })

    return ok_response({
        "routes": routes,
        "recommended": best,
        "signal_states": states,
        "message": "Route recalculated due to traffic event",
    })


# ---------------------------------------------------------------------------
# Traffic event simulation endpoint
# ---------------------------------------------------------------------------

@app.route("/api/traffic/event", methods=["POST"])
def traffic_event():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    event_type = payload.get("event_type")
    location_node = payload.get("location_node")

    if event_type not in TRAFFIC_EVENT_TYPES:
        return error_response(f"event_type must be one of {sorted(TRAFFIC_EVENT_TYPES)}", 400)
    if not location_node:
        return error_response("location_node is required", 400)

    route_optimizer.apply_traffic_event(event_type, location_node)
    description = f"{event_type.replace('_', ' ').title()} reported near {route_optimizer.node_label(location_node)}"
    db.save_traffic_event(request_id, event_type, location_node, description)

    return ok_response({"message": description, "event_type": event_type, "location_node": location_node})


@app.route("/api/traffic/event/reset", methods=["POST"])
def reset_traffic_events():
    route_optimizer.reset_events()
    return ok_response({"message": "All simulated traffic events cleared"})


# ---------------------------------------------------------------------------
# Vehicle simulation endpoint
# ---------------------------------------------------------------------------

@app.route("/api/vehicle/simulate", methods=["POST"])
def simulate_vehicle_step():
    payload = request.get_json(silent=True) or {}
    request_id = payload.get("request_id")
    if not request_id:
        return error_response("request_id is required", 400)
    try:
        state = simulation_engine.step(request_id)
    except KeyError as e:
        return error_response(str(e), 400)

    state["path_labels"] = [route_optimizer.node_label(n) for n in state["path_nodes"]]
    state["current_node_label"] = route_optimizer.node_label(state["current_node"])
    if state["next_node"]:
        state["next_node_label"] = route_optimizer.node_label(state["next_node"])

    return ok_response({"vehicle_state": state})


# ---------------------------------------------------------------------------
# Dashboard summary endpoint
# ---------------------------------------------------------------------------

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    stats = db.get_dashboard_stats()
    return ok_response({
        "stats": stats,
        "model_loaded": predictor.is_loaded,
        "model_metrics": predictor.metrics,
        "simulation_mode": SIMULATION_MODE_LABEL,
    })


@app.route("/api/network", methods=["GET"])
def get_network():
    return ok_response({"network": route_optimizer.network})


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return error_response("Resource not found", 404)


@app.errorhandler(500)
def server_error(e):
    return error_response("Internal server error", 500)


if __name__ == "__main__":
    print(f"ML model loaded: {predictor.is_loaded}")
    if not predictor.is_loaded:
        print(f"WARNING: {predictor.load_error}")
    app.run(debug=True, use_reloader=False, host="127.0.0.1", port=5000)
