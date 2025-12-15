#!/usr/bin/env python3
"""
Truncate vehicles, positions, histories, and geofences to start fresh.
"""
import argparse
import os
import sys
import time

import psycopg2


DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleet")


def wipe(conn):
    start = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(
            """
            TRUNCATE TABLE
              vehicle_position_history,
              vehicle_positions,
              vehicles,
              geofences
            RESTART IDENTITY CASCADE;
            """
        )
    conn.commit()
    return time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description="Wipe vehicles and geofences (truncates tables).")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    if not args.force:
        confirm = input("This will TRUNCATE vehicles/geofences and related tables. Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

    try:
        conn = psycopg2.connect(DB_DSN)
    except Exception as exc:
        print(f"Failed to connect to database at {DB_DSN}: {exc}")
        sys.exit(1)

    try:
        elapsed = wipe(conn)
        print(f"Wiped vehicles and geofences in {elapsed:.3f}s.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
