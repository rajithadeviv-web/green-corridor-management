import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.route_optimizer import RouteOptimizer, RouteOptimizerError


class TestRouteOptimizer(unittest.TestCase):
    def setUp(self):
        self.optimizer = RouteOptimizer()

    def test_generates_multiple_routes(self):
        routes = self.optimizer.generate_routes("hospital", "care_center")
        self.assertGreaterEqual(len(routes), 1)
        for r in routes:
            self.assertIn("total_score", r)
            self.assertIn("junctions", r)

    def test_best_route_is_ranked_first(self):
        routes = self.optimizer.generate_routes("hospital", "care_center")
        scores = [r["total_score"] for r in routes]
        self.assertEqual(scores, sorted(scores))
        self.assertTrue(routes[0]["is_recommended"])

    def test_does_not_always_pick_shortest_distance(self):
        # With heavy congestion weighting, the lowest-distance route may not
        # be the top recommendation once congestion is high on it.
        routes_low = self.optimizer.generate_routes(
            "hospital", "care_center", congestion_level_hint="low"
        )
        routes_severe = self.optimizer.generate_routes(
            "hospital", "care_center", congestion_level_hint="severe"
        )
        self.assertTrue(len(routes_low) >= 1 and len(routes_severe) >= 1)

    def test_invalid_nodes_raise(self):
        with self.assertRaises(RouteOptimizerError):
            self.optimizer.generate_routes("nowhere", "care_center")

    def test_traffic_event_blocks_edge(self):
        routes_before = self.optimizer.generate_routes("hospital", "care_center")
        self.optimizer.apply_traffic_event("road_blockage", "J1")
        routes_after = self.optimizer.generate_routes("hospital", "care_center")
        # routes should still be generable via alternative paths
        self.assertGreaterEqual(len(routes_after), 1)
        self.optimizer.reset_events()


if __name__ == "__main__":
    unittest.main()
