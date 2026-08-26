"""
corridor_manager.py
---------------------
Manages the SIMULATED green corridor: assigns priority state to the
signals (junctions) along a selected route, in the order the emergency
vehicle will reach them, and releases them again after the vehicle passes.

IMPORTANT: This module only simulates signal state in the application's
own database. It does not and cannot control any physical traffic
signal hardware. See SIMULATION_MODE_LABEL below, shown in the UI.
"""

from database import database as db

SIMULATION_MODE_LABEL = "SIMULATION MODE — NO PHYSICAL SIGNALS CONNECTED"

SIGNAL_STATE_NORMAL = "normal"
SIGNAL_STATE_PRIORITY_GREEN = "priority_green"
SIGNAL_STATE_HOLD_RED = "hold_red_for_cross_traffic"


class CorridorManager:
    def activate_corridor(self, request_id: int, junctions: list) -> list:
        """Assign priority-green state, in order, to every junction on the route.
        Returns the resulting signal state list."""
        states = []
        for order, junction_id in enumerate(junctions):
            db.upsert_signal_state(request_id, junction_id, SIGNAL_STATE_PRIORITY_GREEN, True)
            states.append({
                "junction_id": junction_id,
                "order": order + 1,
                "state": SIGNAL_STATE_PRIORITY_GREEN,
                "is_priority": True,
            })
        db.update_request_status(request_id, "corridor_active")
        return states

    def advance_vehicle_past_junction(self, request_id: int, passed_junction_id: str):
        """Called when the simulated vehicle passes a junction: that signal
        returns to normal while later junctions remain priority-green."""
        db.upsert_signal_state(request_id, passed_junction_id, SIGNAL_STATE_NORMAL, False)

    def release_corridor(self, request_id: int, junctions: list):
        """Restore every junction on the route back to normal operation."""
        for junction_id in junctions:
            db.upsert_signal_state(request_id, junction_id, SIGNAL_STATE_NORMAL, False)
        db.update_request_status(request_id, "completed")

    def get_corridor_status(self, request_id: int) -> list:
        return db.get_signal_states(request_id)


corridor_manager = CorridorManager()
