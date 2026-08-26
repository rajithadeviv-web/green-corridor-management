"""
route_optimizer.py
--------------------
Loads the simulated road network graph and generates multiple candidate
routes between a source and destination node. Each route is scored using
a configurable weighted formula (NOT simply shortest-distance).

Route Score (lower is better) =
    W_TIME   * normalized_travel_time
  + W_TRAFFIC* normalized_congestion
  + W_DIST   * normalized_distance
  + W_SIGNAL * signal_delay_penalty
"""

import itertools
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETWORK_PATH = os.path.join(BASE_DIR, "data", "road_network.json")

# Configurable scoring weights (sum does not need to equal 1)
DEFAULT_WEIGHTS = {
    "travel_time": 0.40,
    "congestion": 0.30,
    "distance": 0.15,
    "signal_delay": 0.15,
}

# Extra seconds of delay assumed per un-prioritized signal at each junction
BASE_SIGNAL_DELAY_SEC = 25
PRIORITY_SIGNAL_DELAY_SEC = 3  # residual delay even with green corridor priority

CONGESTION_MULTIPLIER = {
    "low": 1.0,
    "medium": 1.25,
    "high": 1.6,
    "severe": 2.1,
}


class RouteOptimizerError(Exception):
    pass


class RouteOptimizer:
    def __init__(self):
        with open(NETWORK_PATH) as f:
            self.network = json.load(f)
        self.nodes = {n["id"]: n for n in self.network["nodes"]}
        self.adjacency = self._build_adjacency(self.network["edges"])
        # Track ad-hoc blocked edges from simulated traffic events
        self.blocked_edges = set()
        self.congestion_overrides = {}  # edge_key -> congestion_level override

    def _build_adjacency(self, edges):
        adjacency = {}
        for e in edges:
            adjacency.setdefault(e["from"], []).append(e)
            # roads are treated as bidirectional for this simulation
            reverse = {**e, "from": e["to"], "to": e["from"]}
            adjacency.setdefault(e["to"], []).append(reverse)
        return adjacency

    def edge_key(self, a, b):
        return tuple(sorted([a, b]))

    def apply_traffic_event(self, event_type: str, location_node: str):
        """Mutates network state so subsequent route calculations reflect the event."""
        if event_type in ("accident", "road_blockage", "road_closure"):
            for edge in self.adjacency.get(location_node, []):
                self.blocked_edges.add(self.edge_key(edge["from"], edge["to"]))
        elif event_type in ("sudden_congestion", "traffic_increase"):
            for edge in self.adjacency.get(location_node, []):
                self.congestion_overrides[self.edge_key(edge["from"], edge["to"])] = "severe"

    def reset_events(self):
        self.blocked_edges.clear()
        self.congestion_overrides.clear()

    def _find_paths(self, source, destination, max_paths=4, max_depth=8):
        """DFS-based enumeration of simple paths (small graph, so this is fine)."""
        paths = []

        def dfs(node, path, visited):
            if len(paths) >= max_paths or len(path) > max_depth:
                return
            if node == destination:
                paths.append(list(path))
                return
            for edge in self.adjacency.get(node, []):
                nxt = edge["to"]
                key = self.edge_key(edge["from"], edge["to"])
                if key in self.blocked_edges:
                    continue
                if nxt in visited:
                    continue
                visited.add(nxt)
                path.append(edge)
                dfs(nxt, path, visited)
                path.pop()
                visited.remove(nxt)

        dfs(source, [], {source})
        return paths

    def _edge_congestion(self, edge, congestion_level_hint):
        key = self.edge_key(edge["from"], edge["to"])
        if key in self.congestion_overrides:
            return self.congestion_overrides[key]
        return congestion_level_hint

    def generate_routes(self, source, destination, congestion_level_hint="medium",
                         weights=None, max_routes=4):
        if source not in self.nodes or destination not in self.nodes:
            raise RouteOptimizerError("Unknown source or destination node")

        weights = weights or DEFAULT_WEIGHTS
        raw_paths = self._find_paths(source, destination, max_paths=max_routes)
        if not raw_paths:
            raise RouteOptimizerError("No available route found between source and destination")

        routes = []
        for path_edges in raw_paths:
            junctions = [e["from"] for e in path_edges[1:]] + []
            # junctions passed through = all intermediate 'from' nodes after the first edge,
            # plus the 'to' of every edge except the final destination
            intersections = []
            for e in path_edges:
                if e["to"] != destination:
                    intersections.append(e["to"])

            total_distance = sum(e["distance_km"] for e in path_edges)
            base_time_min = sum(e["base_time_min"] for e in path_edges)

            worst_congestion = "low"
            congestion_rank = {"low": 0, "medium": 1, "high": 2, "severe": 3}
            for e in path_edges:
                c = self._edge_congestion(e, congestion_level_hint)
                if congestion_rank[c] > congestion_rank[worst_congestion]:
                    worst_congestion = c

            congestion_mult = CONGESTION_MULTIPLIER[worst_congestion]
            travel_time_min = round(base_time_min * congestion_mult, 2)

            signal_delay_sec = len(intersections) * BASE_SIGNAL_DELAY_SEC
            signal_delay_min = round(signal_delay_sec / 60, 2)

            routes.append({
                "junctions": intersections,
                "path_nodes": [path_edges[0]["from"]] + [e["to"] for e in path_edges],
                "distance_km": round(total_distance, 2),
                "base_travel_time_min": round(base_time_min, 2),
                "estimated_travel_time_min": travel_time_min,
                "congestion_level": worst_congestion,
                "num_intersections": len(intersections),
                "signal_delay_min": signal_delay_min,
            })

        # --- Normalize and score ---
        max_time = max(r["estimated_travel_time_min"] for r in routes) or 1
        max_dist = max(r["distance_km"] for r in routes) or 1
        max_signal = max(r["signal_delay_min"] for r in routes) or 1
        congestion_rank = {"low": 0, "medium": 1, "high": 2, "severe": 3}
        max_cong_rank = 3

        for r in routes:
            norm_time = r["estimated_travel_time_min"] / max_time
            norm_dist = r["distance_km"] / max_dist
            norm_signal = r["signal_delay_min"] / max_signal
            norm_congestion = congestion_rank[r["congestion_level"]] / max_cong_rank

            score = (
                weights["travel_time"] * norm_time
                + weights["congestion"] * norm_congestion
                + weights["distance"] * norm_dist
                + weights["signal_delay"] * norm_signal
            )
            r["total_score"] = round(score * 100, 2)  # 0-100, lower is better
            r["score_breakdown"] = {
                "travel_time_component": round(weights["travel_time"] * norm_time * 100, 2),
                "congestion_component": round(weights["congestion"] * norm_congestion * 100, 2),
                "distance_component": round(weights["distance"] * norm_dist * 100, 2),
                "signal_delay_component": round(weights["signal_delay"] * norm_signal * 100, 2),
            }

        routes.sort(key=lambda r: r["total_score"])
        for i, r in enumerate(routes):
            r["rank"] = i + 1
            r["is_recommended"] = (i == 0)

        return routes

    def node_label(self, node_id):
        return self.nodes.get(node_id, {}).get("label", node_id)


# Singleton reused across requests; network JSON is small and cheap to hold in memory
route_optimizer = RouteOptimizer()
