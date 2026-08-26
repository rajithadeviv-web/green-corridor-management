"""
emergency_manager.py
----------------------
Handles creation and validation of emergency vehicle requests, and maps
configurable emergency levels to numeric priority scores.
"""

from database import database as db

# Configurable priority mapping (not hard-coded throughout the codebase)
EMERGENCY_LEVEL_PRIORITY = {
    "critical": 100,
    "high": 75,
    "medium": 50,
    "normal": 25,
}

VALID_VEHICLE_TYPES = {"ambulance", "fire_engine", "police", "rescue", "other"}


class EmergencyManagerError(Exception):
    pass


class EmergencyManager:
    def validate_request(self, payload: dict):
        errors = []
        vehicle_id = payload.get("vehicle_id")
        vehicle_type = payload.get("vehicle_type")
        source = payload.get("source")
        destination = payload.get("destination")
        emergency_level = payload.get("emergency_level")

        if not vehicle_id or not isinstance(vehicle_id, str):
            errors.append("vehicle_id is required")
        if vehicle_type not in VALID_VEHICLE_TYPES:
            errors.append(f"vehicle_type must be one of {sorted(VALID_VEHICLE_TYPES)}")
        if not source:
            errors.append("source is required")
        if not destination:
            errors.append("destination is required")
        if source == destination:
            errors.append("source and destination must differ")
        if emergency_level not in EMERGENCY_LEVEL_PRIORITY:
            errors.append(f"emergency_level must be one of {sorted(EMERGENCY_LEVEL_PRIORITY)}")

        if errors:
            raise EmergencyManagerError("; ".join(errors))

        if db.has_active_duplicate(vehicle_id):
            raise EmergencyManagerError(
                f"Vehicle '{vehicle_id}' already has an active emergency request"
            )

    def create_request(self, payload: dict) -> int:
        self.validate_request(payload)
        priority_score = EMERGENCY_LEVEL_PRIORITY[payload["emergency_level"]]
        request_id = db.create_emergency_request(
            vehicle_id=payload["vehicle_id"],
            vehicle_type=payload["vehicle_type"],
            source_node=payload["source"],
            destination_node=payload["destination"],
            emergency_level=payload["emergency_level"],
            priority_score=priority_score,
        )
        return request_id


emergency_manager = EmergencyManager()
