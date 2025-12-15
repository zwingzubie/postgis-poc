#!/usr/bin/env python3
"""
Find the geofences containing the most vehicles and optionally loop every N seconds.
"""
import argparse
import os
import sys
import time

import psycopg2


DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleet")


def fetch_top_geofences(cur, top_n: int):
    cur.execute(
        """
        WITH counts AS (
            SELECT g.id, COUNT(vp.vehicle_id) AS vehicle_count
            FROM geofences g
            LEFT JOIN vehicle_positions vp ON ST_Contains(g.geom, vp.geom)
            GROUP BY g.id
        )
        SELECT g.id, g.name, g.fence_type, g.tags, c.vehicle_count
        FROM counts c
        JOIN geofences g ON g.id = c.id
        ORDER BY c.vehicle_count DESC, g.id ASC
        LIMIT %s;
        """,
        (top_n,),
    )
    return cur.fetchall()


def fetch_sample_vehicles(cur, geofence_id: int, limit: int):
    cur.execute(
        """
        SELECT v.id, v.vin, v.license_plate, vp.latitude, vp.longitude
        FROM geofences g
        JOIN vehicle_positions vp ON ST_Contains(g.geom, vp.geom)
        JOIN vehicles v ON v.id = vp.vehicle_id
        WHERE g.id = %s
        ORDER BY v.id
        LIMIT %s;
        """,
        (geofence_id, limit),
    )
    return cur.fetchall()


def run_once(conn, top_n: int, sample_limit: int):
    start = time.perf_counter()
    with conn.cursor() as cur:
        tops = fetch_top_geofences(cur, top_n)
        geofences = []
        for geofence_id, name, fence_type, tags, vehicle_count in tops:
            vehicles = fetch_sample_vehicles(cur, geofence_id, sample_limit) if sample_limit > 0 else []
            geofences.append(
                {
                    "id": geofence_id,
                    "name": name,
                    "fence_type": fence_type,
                    "tags": tags,
                    "vehicle_count": vehicle_count,
                    "vehicles": vehicles,
                }
            )
    elapsed = time.perf_counter() - start
    return geofences, elapsed


def print_result(geofences, elapsed_seconds: float):
    if not geofences:
        print("No geofences found.")
        return
    print(f"Query time: {elapsed_seconds:.3f}s")
    for geofence in geofences:
        print(
            f"Geofence {geofence['id']} | name={geofence['name']} | type={geofence['fence_type']} | "
            f"vehicles={geofence['vehicle_count']} | tags={geofence['tags']}"
        )
        vehicles = geofence["vehicles"]
        if not vehicles:
            print("  No vehicles currently inside.")
            continue
        print("  Sample vehicles (id | vin | plate | lat | lon):")
        for veh_id, vin, plate, lat, lon in vehicles:
            print(f"    {veh_id} | {vin} | {plate} | {lat:.5f} | {lon:.5f}")


def main():
    parser = argparse.ArgumentParser(
        description="Return the geofences with the most vehicles, optionally looping."
    )
    parser.add_argument("--top", type=int, default=1, help="How many top geofences to return (default 1).")
    parser.add_argument("--sample", type=int, default=10, help="Sample vehicles to show (default 10).")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between loops (default 300).")
    args = parser.parse_args()

    try:
        conn = psycopg2.connect(DB_DSN)
        conn.autocommit = True
    except Exception as exc:
        print(f"Failed to connect to database at {DB_DSN}: {exc}")
        sys.exit(1)

    try:
        while True:
            geofences, elapsed = run_once(conn, args.top, args.sample)
            print_result(geofences, elapsed)
            if not args.loop:
                break
            time.sleep(args.interval)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
