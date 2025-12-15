#!/usr/bin/env python3
"""
Fuzzy search vehicles by VIN or license plate (pg_trgm) with timing.
"""
import argparse
import os
import sys
import time

import psycopg2


DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleet")


def search_by_vin(cur, vin_query: str, limit: int):
    start = time.perf_counter()
    cur.execute(
        """
        SELECT v.id,
               v.vin,
               v.license_plate,
               v.make,
               v.model,
               v.year,
               similarity(v.vin, %s) AS score
        FROM vehicles v
        WHERE v.vin %% %s
        ORDER BY score DESC, v.id
        LIMIT %s;
        """,
        (vin_query, vin_query, limit),
    )
    rows = cur.fetchall()
    return rows, time.perf_counter() - start


def search_by_plate(cur, plate_query: str, limit: int):
    start = time.perf_counter()
    cur.execute(
        """
        SELECT v.id,
               v.vin,
               v.license_plate,
               v.make,
               v.model,
               v.year,
               similarity(v.license_plate, %s) AS score
        FROM vehicles v
        WHERE v.license_plate %% %s
        ORDER BY score DESC, v.id
        LIMIT %s;
        """,
        (plate_query, plate_query, limit),
    )
    rows = cur.fetchall()
    return rows, time.perf_counter() - start


def main():
    parser = argparse.ArgumentParser(description="Fuzzy search vehicles by VIN or license plate.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--vin", type=str, help="VIN to fuzzy match.")
    group.add_argument("--plate", type=str, help="License plate to fuzzy match.")
    parser.add_argument("--limit", type=int, default=10, help="Max results to show (default 10).")
    args = parser.parse_args()

    try:
        conn = psycopg2.connect(DB_DSN)
    except Exception as exc:
        print(f"Failed to connect to database at {DB_DSN}: {exc}")
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            if args.vin:
                rows, elapsed = search_by_vin(cur, args.vin, args.limit)
                label = f'VIN "{args.vin}"'
            else:
                rows, elapsed = search_by_plate(cur, args.plate, args.limit)
                label = f'plate "{args.plate}"'

        if not rows:
            print(f"No vehicles matched {label}.")
            return

        print(f"Matches for {label}:")
        print("vehicle_id | vin | license_plate | make | model | year | similarity")
        for row in rows:
            vehicle_id, vin, plate, make, model, year, score = row
            print(f"{vehicle_id} | {vin} | {plate} | {make} | {model} | {year} | {score:.3f}")
        print(f"Query time: {elapsed:.3f}s")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
