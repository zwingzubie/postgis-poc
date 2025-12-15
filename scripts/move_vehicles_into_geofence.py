#!/usr/bin/env python3
"""
Move a set of vehicles into a specific geofence by updating their positions.
"""
import argparse
import os
import sys
import time

import psycopg2


DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleet")


def move_into_geofence(conn, geofence_id: int, count: int):
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM geofences WHERE id = %s", (geofence_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Geofence {geofence_id} not found.")
        name = row[0]

        cur.execute(
            """
            WITH geofence AS (
                SELECT geom FROM geofences WHERE id = %(geofence_id)s
            ),
            sampled AS (
                SELECT id AS vehicle_id
                FROM vehicles
                ORDER BY random()
                LIMIT %(count)s
            ),
            points AS (
                SELECT s.vehicle_id,
                       (SELECT (ST_Dump(ST_GeneratePoints(g.geom, 1))).geom FROM geofence g) AS geom
                FROM sampled s
            ),
            updated AS (
                UPDATE vehicle_positions vp
                SET geom = p.geom,
                    latitude = ST_Y(p.geom),
                    longitude = ST_X(p.geom),
                    heading_deg = 0,
                    speed_kph = 0,
                    updated_at = now()
                FROM points p
                WHERE vp.vehicle_id = p.vehicle_id
                RETURNING vp.vehicle_id, vp.geom, vp.latitude, vp.longitude, vp.heading_deg, vp.speed_kph, vp.updated_at
            )
            INSERT INTO vehicle_position_history (vehicle_id, geom, latitude, longitude, heading_deg, speed_kph, recorded_at)
            SELECT vehicle_id, geom, latitude, longitude, heading_deg, speed_kph, updated_at
            FROM updated;
            """,
            {"geofence_id": geofence_id, "count": count},
        )
        moved = cur.rowcount
    conn.commit()
    elapsed = time.perf_counter() - start
    return name, moved, elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Move a set of vehicles into a geofence."
    )
    parser.add_argument("--geofence-id", type=int, required=True, help="Target geofence id.")
    parser.add_argument("--count", type=int, default=100, help="Number of vehicles to move (default 100).")
    args = parser.parse_args()

    try:
        conn = psycopg2.connect(DB_DSN)
    except Exception as exc:
        print(f"Failed to connect to database at {DB_DSN}: {exc}")
        sys.exit(1)

    try:
        name, moved, elapsed = move_into_geofence(conn, args.geofence_id, args.count)
        print(f"Moved {moved} vehicles into geofence {args.geofence_id} ({name}) in {elapsed:.3f}s.")
    except ValueError as exc:
        print(exc)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
