import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point the database module at a temp file BEFORE importing modules that use it
import database.database as db_module
_tmp_dir = tempfile.mkdtemp()
db_module.DB_PATH = os.path.join(_tmp_dir, "test_green_corridor.db")

from database import database as db
from services.corridor_manager import CorridorManager, SIMULATION_MODE_LABEL
from services.emergency_manager import EmergencyManager, EmergencyManagerError


class TestCorridorAndEmergency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()

    def setUp(self):
        self.corridor = CorridorManager()
        self.emergency = EmergencyManager()

    def test_create_emergency_request_valid(self):
        request_id = self.emergency.create_request({
            "vehicle_id": "TEST-AMB-1",
            "vehicle_type": "ambulance",
            "source": "hospital",
            "destination": "care_center",
            "emergency_level": "critical",
        })
        self.assertIsInstance(request_id, int)
        req = db.get_request(request_id)
        self.assertEqual(req["priority_score"], 100)

    def test_duplicate_active_request_rejected(self):
        self.emergency.create_request({
            "vehicle_id": "TEST-AMB-DUP",
            "vehicle_type": "ambulance",
            "source": "hospital",
            "destination": "care_center",
            "emergency_level": "high",
        })
        with self.assertRaises(EmergencyManagerError):
            self.emergency.create_request({
                "vehicle_id": "TEST-AMB-DUP",
                "vehicle_type": "ambulance",
                "source": "hospital",
                "destination": "care_center",
                "emergency_level": "high",
            })

    def test_invalid_vehicle_type_rejected(self):
        with self.assertRaises(EmergencyManagerError):
            self.emergency.create_request({
                "vehicle_id": "TEST-BAD",
                "vehicle_type": "spaceship",
                "source": "hospital",
                "destination": "care_center",
                "emergency_level": "high",
            })

    def test_same_source_destination_rejected(self):
        with self.assertRaises(EmergencyManagerError):
            self.emergency.create_request({
                "vehicle_id": "TEST-SAME",
                "vehicle_type": "ambulance",
                "source": "hospital",
                "destination": "hospital",
                "emergency_level": "high",
            })

    def test_corridor_activation_and_signal_states(self):
        request_id = self.emergency.create_request({
            "vehicle_id": "TEST-AMB-CORRIDOR",
            "vehicle_type": "ambulance",
            "source": "hospital",
            "destination": "care_center",
            "emergency_level": "critical",
        })
        junctions = ["J1", "J2", "J3"]
        states = self.corridor.activate_corridor(request_id, junctions)
        self.assertEqual(len(states), 3)
        for s in states:
            self.assertEqual(s["state"], "priority_green")

        db_states = self.corridor.get_corridor_status(request_id)
        self.assertEqual(len(db_states), 3)
        self.assertTrue(all(s["is_priority"] == 1 for s in db_states))

    def test_corridor_release_restores_normal(self):
        request_id = self.emergency.create_request({
            "vehicle_id": "TEST-AMB-RELEASE",
            "vehicle_type": "ambulance",
            "source": "hospital",
            "destination": "care_center",
            "emergency_level": "critical",
        })
        junctions = ["J1", "J2"]
        self.corridor.activate_corridor(request_id, junctions)
        self.corridor.release_corridor(request_id, junctions)

        db_states = self.corridor.get_corridor_status(request_id)
        self.assertTrue(all(s["is_priority"] == 0 for s in db_states))
        req = db.get_request(request_id)
        self.assertEqual(req["status"], "completed")

    def test_simulation_mode_label_present(self):
        self.assertIn("SIMULATION", SIMULATION_MODE_LABEL)
        self.assertIn("NO PHYSICAL SIGNALS", SIMULATION_MODE_LABEL)


if __name__ == "__main__":
    unittest.main()
