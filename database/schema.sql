-- schema.sql
-- SQLite schema for the AI-Based Green Corridor Management prototype.

CREATE TABLE IF NOT EXISTS emergency_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id TEXT NOT NULL,
    vehicle_type TEXT NOT NULL,
    source_node TEXT NOT NULL,
    destination_node TEXT NOT NULL,
    emergency_level TEXT NOT NULL,
    priority_score INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    route_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    eta_minutes REAL,
    distance_km REAL
);

CREATE TABLE IF NOT EXISTS traffic_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    vehicle_count INTEGER,
    traffic_density REAL,
    average_speed REAL,
    road_length REAL,
    hour INTEGER,
    day_of_week INTEGER,
    weather TEXT,
    road_capacity INTEGER,
    predicted_congestion TEXT,
    congestion_score REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES emergency_requests (id)
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    route_json TEXT NOT NULL,
    is_selected INTEGER NOT NULL DEFAULT 0,
    total_score REAL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES emergency_requests (id)
);

CREATE TABLE IF NOT EXISTS signal_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    junction_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'normal',
    is_priority INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES emergency_requests (id)
);

CREATE TABLE IF NOT EXISTS traffic_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    event_type TEXT NOT NULL,
    location_node TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES emergency_requests (id)
);

CREATE TABLE IF NOT EXISTS completed_trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    vehicle_id TEXT NOT NULL,
    total_time_min REAL,
    estimated_time_saved_min REAL,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES emergency_requests (id)
);
