#!/usr/bin/env python3
"""
Seed the local PostGIS database with vehicles, geofences, and initial position history.

Defaults:
- 60,000 vehicles
- 120,000 geofences

You can override counts via VEHICLE_COUNT and GEOFENCE_COUNT env vars.
"""
import os
import random
import sys
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import Json, execute_values


DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/fleet")
VEHICLE_COUNT = int(os.getenv("VEHICLE_COUNT", "60000"))
GEOFENCE_COUNT = int(os.getenv("GEOFENCE_COUNT", "120000"))


VIN_CHARS = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
LICENSE_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MAKES_MODELS = {
    "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Tacoma"],
    "Ford": ["F-150", "Explorer", "Escape", "Mustang", "Edge"],
    "Chevrolet": ["Silverado", "Equinox", "Tahoe", "Traverse", "Bolt"],
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "Ridgeline"],
    "Nissan": ["Altima", "Rogue", "Sentra", "Pathfinder", "Frontier"],
    "BMW": ["330i", "X3", "X5", "M4", "i4"],
    "Mercedes": ["C300", "GLC", "GLE", "EQS", "Sprinter"],
    "Tesla": ["Model 3", "Model Y", "Model S", "Model X"],
    "Jeep": ["Wrangler", "Grand Cherokee", "Compass", "Gladiator"],
    "Subaru": ["Outback", "Forester", "Crosstrek", "WRX"],
    "Hyundai": ["Santa Fe", "Tucson", "Kona", "Elantra"],
    "Kia": ["Telluride", "Sorento", "Sportage", "EV6"],
    "Volkswagen": ["Jetta", "Golf", "Tiguan", "Atlas"],
    "Volvo": ["XC40", "XC60", "XC90", "S60"],
    "Audi": ["A4", "Q5", "Q7", "e-tron"],
    "Lexus": ["RX350", "NX300", "IS300", "GX460"],
    "Mazda": ["CX-5", "CX-50", "CX-30", "Mazda3"],
    "GMC": ["Sierra", "Yukon", "Acadia", "Canyon"],
    "Dodge": ["Ram", "Durango", "Charger"],
    "Cadillac": ["Escalade", "XT5", "Lyriq"],
}
COLORS = ["black", "white", "silver", "gray", "blue", "red", "green", "orange", "navy", "gold"]
FLEETS = ["alpha", "bravo", "charlie", "delta", "omega", "metro", "rural", "long-haul"]
GEOFENCE_TYPES = ["warehouse", "customer", "yard", "hub", "service-area", "restricted", "depot"]
GEOFENCE_TAGS = ["priority", "urban", "suburban", "high-traffic", "rural", "cold", "hot", "coastal", "mountain"]
CITY_NAMES = [
    "Seattle", "Portland", "San Francisco", "Los Angeles", "San Diego", "Phoenix", "Denver", "Dallas",
    "Houston", "Austin", "Chicago", "Detroit", "Boston", "New York", "Philadelphia", "Baltimore", "Charlotte",
    "Miami", "Orlando", "Atlanta", "Nashville", "Cleveland", "Pittsburgh", "Columbus", "Indianapolis",
    "Kansas City", "St Louis", "Minneapolis", "Omaha", "Boise", "Salt Lake", "Las Vegas", "Reno",
    "Birmingham", "New Orleans", "Memphis", "Richmond", "Buffalo", "Albany", "Hartford", "Providence",
    "Raleigh", "Charleston", "Savannah", "Tampa", "Tucson", "El Paso", "Anchorage", "Honolulu"
]
ADJECTIVES = ["North", "South", "East", "West", "Central", "Upper", "Lower", "River", "Lake", "Harbor", "Gateway"]


def random_vin() -> str:
    return "".join(random.choice(VIN_CHARS) for _ in range(17))


def random_plate() -> str:
    left = "".join(random.choice(LICENSE_CHARS) for _ in range(3))
    right = "".join(str(random.randint(0, 9)) for _ in range(4))
    return f"{left}-{right}"


def random_point():
    # Continental US bounds
    lat = random.uniform(24.5, 49.5)
    lon = random.uniform(-124.8, -66.9)
    return lat, lon


def random_polygon():
    lat, lon = random_point()
    size = random.uniform(0.01, 0.12)  # roughly 1-12km squares
    coords = [
        (lon - size, lat - size),
        (lon + size, lat - size),
        (lon + size, lat + size),
        (lon - size, lat + size),
        (lon - size, lat - size),
    ]
    coord_str = ", ".join(f"{x} {y}" for x, y in coords)
    return f"POLYGON(({coord_str}))"


def vehicle_metadata(make: str, model: str) -> dict:
    return {
        "fleet": random.choice(FLEETS),
        "status": random.choice(["active", "maintenance", "idle"]),
        "fuel": random.choice(["gasoline", "diesel", "hybrid", "electric"]),
        "trim": random.choice(["base", "sport", "luxury", "offroad"]),
        "odometer_km": random.randint(1_000, 250_000),
        "vin_source": random.choice(["oem", "aftermarket", "telematics"]),
        "make": make,
        "model": model,
    }


def geofence_metadata(fence_type: str) -> dict:
    return {
        "speed_limit_kph": random.choice([25, 35, 45, 55, 65]),
        "access": random.choice(["public", "private", "staff-only", "customer"]),
        "priority": random.choice(["critical", "normal", "low"]),
        "timezone": random.choice(["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"]),
        "notes": random.choice(["staging", "inbound", "outbound", "mixed", "overnight"]),
        "fence_type": fence_type,
    }


def connect():
    return psycopg2.connect(DB_DSN)


def load_existing_vehicle_keys(conn):
    """Return existing VINs and license plates to avoid unique constraint errors."""
    with conn.cursor() as cur:
        cur.execute("SELECT vin, license_plate FROM vehicles")
        rows = cur.fetchall()
    vins = {row[0] for row in rows}
    plates = {row[1] for row in rows}
    return vins, plates


def seed_geofences(conn, total: int):
    print(f"Creating {total:,} geofences...")
    batch_size = 2000
    created = 0
    random.seed(42)
    with conn.cursor() as cur:
        while created < total:
            rows = []
            count = min(batch_size, total - created)
            for i in range(count):
                fence_type = random.choice(GEOFENCE_TYPES)
                city = random.choice(CITY_NAMES)
                name = f"{random.choice(ADJECTIVES)} {city} Zone {created + i}"
                tags = list({random.choice(GEOFENCE_TAGS) for _ in range(3)})
                meta = geofence_metadata(fence_type)
                wkt = random_polygon()
                rows.append((name, fence_type, tags, Json(meta), wkt))

            execute_values(
                cur,
                """
                INSERT INTO geofences (name, fence_type, tags, metadata, geom)
                VALUES %s
                """,
                rows,
                template="(%s, %s, %s, %s, ST_GeomFromText(%s, 4326))",
                page_size=500,
            )
            conn.commit()
            created += count
            if created % 10000 == 0 or created == total:
                print(f"  geofences: {created:,}/{total:,}")
    print("Geofences done.")


def seed_vehicles(conn, total: int):
    print(f"Creating {total:,} vehicles with positions and history...")
    batch_size = 2000
    created = 0
    random.seed(99)
    make_names = list(MAKES_MODELS.keys())
    seen_vins, seen_plates = load_existing_vehicle_keys(conn)

    with conn.cursor() as cur:
        while created < total:
            rows = []
            positions = []
            count = min(batch_size, total - created)
            for _ in range(count):
                make = random.choice(make_names)
                model = random.choice(MAKES_MODELS[make])
                year = random.randint(2005, datetime.now(timezone.utc).year)
                color = random.choice(COLORS)
                vin = random_vin()
                while vin in seen_vins:
                    vin = random_vin()
                seen_vins.add(vin)

                plate = random_plate()
                while plate in seen_plates:
                    plate = random_plate()
                seen_plates.add(plate)
                meta = vehicle_metadata(make, model)
                lat, lon = random_point()
                heading = random.uniform(0, 360)
                speed = max(0, random.gauss(60, 20))
                rows.append((vin, plate, make, model, year, color, Json(meta)))
                positions.append((lon, lat, heading, speed))

            ids = execute_values(
                cur,
                """
                INSERT INTO vehicles (vin, license_plate, make, model, year, color, metadata)
                VALUES %s
                RETURNING id
                """,
                rows,
                page_size=500,
                fetch=True,
            )

            pos_template = "(%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, now())"
            hist_template = "(%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, now())"
            position_rows = []
            history_rows = []
            for (veh_id,), (lon, lat, heading, speed) in zip(ids, positions):
                position_rows.append((veh_id, lon, lat, lat, lon, heading, speed))
                history_rows.append((veh_id, lon, lat, lat, lon, heading, speed))

            execute_values(
                cur,
                """
                INSERT INTO vehicle_positions (vehicle_id, geom, latitude, longitude, heading_deg, speed_kph, updated_at)
                VALUES %s
                """,
                position_rows,
                template=pos_template,
                page_size=500,
            )
            execute_values(
                cur,
                """
                INSERT INTO vehicle_position_history (vehicle_id, geom, latitude, longitude, heading_deg, speed_kph, recorded_at)
                VALUES %s
                """,
                history_rows,
                template=hist_template,
                page_size=500,
            )
            conn.commit()
            created += count
            if created % 10000 == 0 or created == total:
                print(f"  vehicles: {created:,}/{total:,}")
    print("Vehicles done.")


def main():
    try:
        conn = connect()
    except Exception as exc:
        print(f"Failed to connect to database at {DB_DSN}: {exc}")
        sys.exit(1)

    try:
        seed_geofences(conn, GEOFENCE_COUNT)
        seed_vehicles(conn, VEHICLE_COUNT)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
