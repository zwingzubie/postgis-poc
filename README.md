# PostGIS POC: Fleet + Geofences

Local Postgres with PostGIS + fuzzy search, seeded with 60k vehicles and 120k geofences. Includes scripts to refresh positions every five minutes and query which vehicles are inside which geofences.

## Prereqs
- Docker + Docker Compose
- Python 3.9+ (`python3 -m venv .venv && source .venv/bin/activate`)

## Run the stack
```bash
# Compose v2 (Docker Desktop / recent CLIs)
docker compose up -d

# If you see "unknown shorthand flag: 'd'" or don't have the v2 plugin, use v1:
docker-compose up -d
```

The database lives at `postgresql://postgres:postgres@localhost:5432/fleet`.

## Install Python deps
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Seed data (60k vehicles, 120k geofences)
```bash
python scripts/seed_data.py
# Or override counts
VEHICLE_COUNT=80000 GEOFENCE_COUNT=150000 python scripts/seed_data.py
```

Data model highlights:
- `vehicles` with VIN, make, model, license plate, metadata
- `vehicle_positions` (current) and `vehicle_position_history` with PostGIS points
- `geofences` with PostGIS polygons, tags, metadata, and trigram index for fuzzy name search

## Keep vehicle positions moving every 5 minutes
```bash
# single update
python scripts/update_positions.py

# loop every 5 minutes
python scripts/update_positions.py --loop --interval 300
```

## Busiest geofences
```bash
# top N geofences by vehicle count (shows query time)
python scripts/top_geofence_by_vehicles.py --top 3 --sample 2

# loop every minute
python scripts/top_geofence_by_vehicles.py --top 5 --sample 1 --loop --interval 60
```

## Find vehicles inside a geofence
```bash
# by id
python scripts/find_vehicles_in_geofence.py --geofence-id 123 --limit 20

# fuzzy by name (pg_trgm)
python scripts/find_vehicles_in_geofence.py --name "Central Seattle Zone" --limit 20

# output includes query time at the end
```

## Move vehicles into a geofence
```bash
python scripts/move_vehicles_into_geofence.py --geofence-id 123 --count 50
```

## Fuzzy search vehicles (VIN or plate)
```bash
python scripts/find_vehicle_fuzzy.py --vin ABC123 --limit 5
python scripts/find_vehicle_fuzzy.py --plate XYZ --limit 10
```

You can also run ad-hoc SQL (requires psql):
```bash
psql "postgresql://postgres:postgres@localhost:5432/fleet" -c "
  SELECT g.id AS geofence_id, g.name, v.id AS vehicle_id, v.vin
  FROM geofences g
  JOIN vehicle_positions vp ON ST_Contains(g.geom, vp.geom)
  JOIN vehicles v ON v.id = vp.vehicle_id
  LIMIT 20;"
```

Fuzzy search example:
```bash
psql "postgresql://postgres:postgres@localhost:5432/fleet" -c "
  SELECT id, name, similarity(name, 'Central Seattle Zone') AS score
  FROM geofences
  WHERE name % 'Central Seattle Zone'
  ORDER BY score DESC
  LIMIT 5;"
```

## Extensions enabled
- postgis / postgis_topology
- pg_trgm (trigram fuzzy search)
- fuzzystrmatch
- unaccent

## Notes
- Database schema and extensions are auto-applied via `db/initdb/*.sql`.
- Data is local only (no network calls). Volume `pgdata` persists database files between runs.
- Seeding 180k+ rows will take a few minutes; keep `docker compose logs -f db` open if you want to watch readiness.
