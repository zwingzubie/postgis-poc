#!/usr/bin/env python3
"""
Move all vehicle positions slightly, persist to history, and optionally loop every N seconds.
"""
import argparse
import os
import sys
import time

import psycopg2


DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleet")


def update_once(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH moved AS (
                UPDATE vehicle_positions vp
                SET geom = new_geom,
                    latitude = ST_Y(new_geom),
                    longitude = ST_X(new_geom),
                    heading_deg = mod((vp.heading_deg + ((random() - 0.5) * 30))::numeric, 360::numeric)::double precision,
                    speed_kph = greatest(0, vp.speed_kph + ((random() - 0.5) * 10)),
                    updated_at = now()
                FROM (
                    SELECT vehicle_id,
                           ST_Transform(
                               ST_Translate(
                                   ST_Transform(geom, 3857),
                                   (random() - 0.5) * 500,
                                   (random() - 0.5) * 500
                               ),
                               4326
                           ) AS new_geom
                    FROM vehicle_positions
                ) calc
                WHERE calc.vehicle_id = vp.vehicle_id
                RETURNING vp.vehicle_id, new_geom AS geom, ST_X(new_geom) AS lon, ST_Y(new_geom) AS lat, heading_deg, speed_kph, updated_at
            )
            INSERT INTO vehicle_position_history (vehicle_id, geom, longitude, latitude, heading_deg, speed_kph, recorded_at)
            SELECT vehicle_id, geom, lon, lat, heading_deg, speed_kph, updated_at FROM moved;
            """
        )
        updated = cur.rowcount
    conn.commit()
    return updated


def main():
    parser = argparse.ArgumentParser(description="Update vehicle positions and append to history.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument("--interval", type=int, default=300, help="Seconds between loops (default 300).")
    args = parser.parse_args()

    try:
        conn = psycopg2.connect(DB_DSN)
    except Exception as exc:
        print(f"Failed to connect to database at {DB_DSN}: {exc}")
        sys.exit(1)

    try:
        while True:
            updated = update_once(conn)
            print(f"Updated {updated:,} vehicle positions.")
            if not args.loop:
                break
            time.sleep(args.interval)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
