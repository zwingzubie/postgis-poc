#!/usr/bin/env python3
"""
Find vehicles inside a geofence by id or fuzzy name.
"""
import argparse
import os
import sys
import time

import psycopg2


DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleet")


def find_by_id(cur, geofence_id: int, limit: int):
    start = time.perf_counter()
    cur.execute(
        """
        SELECT g.id, g.name, v.id AS vehicle_id, v.vin, v.license_plate, vp.latitude, vp.longitude
        FROM geofences g
        JOIN vehicle_positions vp ON ST_Contains(g.geom, vp.geom)
        JOIN vehicles v ON v.id = vp.vehicle_id
        WHERE g.id = %s
        ORDER BY v.id
        LIMIT %s;
        """,
        (geofence_id, limit),
    )
    rows = cur.fetchall()
    return rows, time.perf_counter() - start


def find_by_name(cur, name: str, limit: int):
    start = time.perf_counter()
    cur.execute(
        """
        WITH target AS (
            SELECT id, name, geom
            FROM geofences
            WHERE name % %s
            ORDER BY similarity(name, %s) DESC
            LIMIT 1
        )
        SELECT t.id, t.name, v.id AS vehicle_id, v.vin, v.license_plate, vp.latitude, vp.longitude
        FROM target t
        JOIN vehicle_positions vp ON ST_Contains(t.geom, vp.geom)
        JOIN vehicles v ON v.id = vp.vehicle_id
        ORDER BY v.id
        LIMIT %s;
        """,
        (name, name, limit),
    )
    rows = cur.fetchall()
    return rows, time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description="Search vehicles inside a geofence.")
    parser.add_argument("--geofence-id", type=int, help="Geofence id to check.")
    parser.add_argument("--name", type=str, help="Fuzzy geofence name search (uses pg_trgm).")
    parser.add_argument("--limit", type=int, default=20, help="Max vehicles to show (default 20).")
    args = parser.parse_args()

    if not args.geofence_id and not args.name:
        print("You must specify --geofence-id or --name.")
        sys.exit(1)

    try:
        conn = psycopg2.connect(DB_DSN)
    except Exception as exc:
        print(f"Failed to connect to database at {DB_DSN}: {exc}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            if args.geofence_id:
                rows, elapsed = find_by_id(cur, args.geofence_id, args.limit)
            else:
                rows, elapsed = find_by_name(cur, args.name, args.limit)
        if not rows:
            print("No vehicles found inside the requested geofence.")
            return
        print("geofence_id | geofence_name | vehicle_id | vin | license_plate | latitude | longitude")
        for row in rows:
            print(" | ".join(str(item) for item in row))
        print(f"Query time: {elapsed:.3f}s")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
