#!/usr/bin/env python3
"""Download and import the OurAirports database for offline airport lookups.

OurAirports publishes free, public CSVs covering ~78,000 airports worldwide
(ICAO + IATA codes, names, cities, countries). We import them into SQLite so
SkyDex can turn a bare code like "KBOS" into "Boston Logan Intl, Boston,
United States" anywhere it shows a route — no per-lookup API calls.

Run manually:
    python3 sync_airports_db.py

Or add to crontab for a monthly refresh:
    0 5 1 * * cd ~/skydex && python3 sync_airports_db.py >> /tmp/skydex_airports_sync.log 2>&1
"""

from __future__ import annotations

import csv
import io
import logging
import os
import sqlite3
import sys
import urllib.request

logger = logging.getLogger("airports_sync")

AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
COUNTRIES_URL = "https://davidmegginson.github.io/ourairports-data/countries.csv"

DEFAULT_DB_PATH = os.path.expanduser("~/.skydex/airports.db")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def download_csv(url: str, timeout: int = 120) -> str:
    logger.info("Downloading %s ...", url)
    req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
    logger.info("  %d bytes", len(data))
    return data


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS airports;
        DROP TABLE IF EXISTS airport_countries;

        CREATE TABLE airports (
            ident        TEXT,   -- usually the ICAO code (e.g. KBOS)
            iata_code    TEXT,   -- IATA code (e.g. BOS)
            name         TEXT,
            municipality TEXT,   -- city
            iso_country  TEXT,   -- ISO 3166-1 alpha-2
            type         TEXT,
            latitude     TEXT,
            longitude    TEXT
        );

        CREATE TABLE airport_countries (
            code TEXT PRIMARY KEY,   -- ISO 3166-1 alpha-2
            name TEXT
        );

        CREATE INDEX idx_airports_ident ON airports(ident);
        CREATE INDEX idx_airports_iata  ON airports(iata_code);
    """)
    conn.commit()


def import_airports(conn: sqlite3.Connection, csv_text: str) -> int:
    reader = csv.DictReader(io.StringIO(csv_text))
    cur = conn.cursor()
    n = 0
    for row in reader:
        ident = (row.get("ident") or "").strip().upper()
        iata = (row.get("iata_code") or "").strip().upper()
        if not ident and not iata:
            continue
        cur.execute(
            "INSERT INTO airports (ident, iata_code, name, municipality, iso_country, type, latitude, longitude) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ident or None,
                iata or None,
                (row.get("name") or "").strip() or None,
                (row.get("municipality") or "").strip() or None,
                (row.get("iso_country") or "").strip().upper() or None,
                (row.get("type") or "").strip() or None,
                (row.get("latitude_deg") or "").strip() or None,
                (row.get("longitude_deg") or "").strip() or None,
            ),
        )
        n += 1
    conn.commit()
    return n


def import_countries(conn: sqlite3.Connection, csv_text: str) -> int:
    reader = csv.DictReader(io.StringIO(csv_text))
    cur = conn.cursor()
    n = 0
    for row in reader:
        code = (row.get("code") or "").strip().upper()
        name = (row.get("name") or "").strip()
        if not code:
            continue
        cur.execute(
            "INSERT OR REPLACE INTO airport_countries (code, name) VALUES (?, ?)",
            (code, name or code),
        )
        n += 1
    conn.commit()
    return n


def main() -> None:
    setup_logging()
    db_path = os.environ.get("AIRPORTS_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info("=" * 50)
    logger.info("OurAirports DB Sync -> %s", db_path)
    logger.info("=" * 50)

    try:
        airports_csv = download_csv(AIRPORTS_URL)
        countries_csv = download_csv(COUNTRIES_URL)

        conn = sqlite3.connect(db_path)
        create_tables(conn)
        a = import_airports(conn, airports_csv)
        c = import_countries(conn, countries_csv)
        conn.close()

        logger.info("=" * 50)
        logger.info("Import complete: %d airports, %d countries", a, c)
        logger.info("=" * 50)
    except Exception as e:
        logger.error("Airport sync failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
