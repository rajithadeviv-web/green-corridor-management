"""
simulation_engine.py
----------------------
Simulates the emergency vehicle's step-by-step movement along its selected
route. On each simulated "tick" (triggered by the frontend), the vehicle
advances to the next node; the corridor manager is told to release the
signal it just passed.

This is a lightweight in-memory simulation keyed by request_id so the
Flask app can support multiple concurrent demo runs without needing a
background scheduler for the prototype.
"""

import time

from services.corridor_manager import corridor_manager

# average simulated speed for ETA calculations (km/h), configurable
SIMULATED_VEHICLE_SPEED_KMH = 45


class SimulationEngine:
    def __init__(self):
        # request_id -> simulation state dict
        self._simulations = {}

    def start(self, request_id: int, route: dict):
        path_nodes = route["path_nodes"]
        self._simulations[request_id] = {
            "path_nodes": path_nodes,
            "current_index": 0,
            "distance_km": route["distance_km"],
            "started_at": time.time(),
            "status": "moving",
        }
        return self.get_state(request_id)

    def step(self, request_id: int):
        sim = self._simulations.get(request_id)
        if not sim:
            raise KeyError(f"No active simulation for request {request_id}")
        if sim["status"] == "completed":
            return self.get_state(request_id)

        path_nodes = sim["path_nodes"]
        current_index = sim["current_index"]

        # The node the vehicle is currently AT is being left behind (passed)
        if 0 < current_index < len(path_nodes):
            passed_node = path_nodes[current_index]
            corridor_manager.advance_vehicle_past_junction(request_id, passed_node)

        if current_index < len(path_nodes) - 1:
            sim["current_index"] += 1

        if sim["current_index"] == len(path_nodes) - 1:
            sim["status"] = "completed"

        return self.get_state(request_id)

    def get_state(self, request_id: int):
        sim = self._simulations.get(request_id)
        if not sim:
            return None
        path_nodes = sim["path_nodes"]
        idx = sim["current_index"]
        remaining_nodes = len(path_nodes) - 1 - idx
        total_nodes = len(path_nodes) - 1
        distance_remaining = (
            round(sim["distance_km"] * (remaining_nodes / total_nodes), 2)
            if total_nodes > 0 else 0
        )
        eta_min = round((distance_remaining / SIMULATED_VEHICLE_SPEED_KMH) * 60, 1)

        return {
            "current_node": path_nodes[idx],
            "next_node": path_nodes[idx + 1] if idx + 1 < len(path_nodes) else None,
            "current_index": idx,
            "total_nodes": len(path_nodes),
            "distance_remaining_km": distance_remaining,
            "eta_minutes": eta_min,
            "status": sim["status"],
            "path_nodes": path_nodes,
        }

    def reset(self, request_id: int):
        self._simulations.pop(request_id, None)


simulation_engine = SimulationEngine()
