-- Core tables for vehicles, geofences, and positions
CREATE TABLE IF NOT EXISTS vehicles (
  id          BIGSERIAL PRIMARY KEY,
  vin         VARCHAR(32) NOT NULL UNIQUE,
  license_plate VARCHAR(16) NOT NULL UNIQUE,
  make        TEXT NOT NULL,
  model       TEXT NOT NULL,
  year        INTEGER NOT NULL,
  color       TEXT,
  metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vehicles_metadata_gin ON vehicles USING gin (metadata);

CREATE TABLE IF NOT EXISTS vehicle_positions (
  vehicle_id  BIGINT PRIMARY KEY REFERENCES vehicles(id) ON DELETE CASCADE,
  geom        geometry(Point, 4326) NOT NULL,
  latitude    DOUBLE PRECISION NOT NULL,
  longitude   DOUBLE PRECISION NOT NULL,
  heading_deg DOUBLE PRECISION NOT NULL DEFAULT 0,
  speed_kph   DOUBLE PRECISION NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_geom ON vehicle_positions USING gist (geom);

CREATE TABLE IF NOT EXISTS vehicle_position_history (
  id          BIGSERIAL PRIMARY KEY,
  vehicle_id  BIGINT NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
  geom        geometry(Point, 4326) NOT NULL,
  latitude    DOUBLE PRECISION NOT NULL,
  longitude   DOUBLE PRECISION NOT NULL,
  heading_deg DOUBLE PRECISION,
  speed_kph   DOUBLE PRECISION,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vehicle_position_history_geom ON vehicle_position_history USING gist (geom);
CREATE INDEX IF NOT EXISTS idx_vehicle_position_history_vehicle_time ON vehicle_position_history (vehicle_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS geofences (
  id         BIGSERIAL PRIMARY KEY,
  name       TEXT NOT NULL,
  fence_type TEXT,
  geom       geometry(Polygon, 4326) NOT NULL,
  tags       TEXT[] NOT NULL DEFAULT '{}',
  metadata   JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_geofences_geom ON geofences USING gist (geom);
CREATE INDEX IF NOT EXISTS idx_geofences_tags_gin ON geofences USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_geofences_name_trgm ON geofences USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_geofences_metadata_gin ON geofences USING gin (metadata);
