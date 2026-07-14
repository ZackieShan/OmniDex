#!/usr/bin/env bash
# SkyDex fresh start — wipe your tracking history and (re)launch.
#
# Clears ONLY your sightings DB (~/.skydex/skydex.db). The FAA / OpenSky
# reference databases are kept (they're enrichment data, not your history) and
# only built if missing — pass --resync to rebuild them too.
#
# Usage:
#   ./fresh_start.sh             # wipe history, run in the foreground
#   ./fresh_start.sh --service   # wipe history, (re)start the systemd services
#   ./fresh_start.sh --resync    # also re-download the FAA + OpenSky reference DBs
#
# First time: chmod +x fresh_start.sh

set -u

SKYDEX_DIR="$HOME/skydex"
DB_DIR="$HOME/.skydex"
PY="python3"

cd "$SKYDEX_DIR" || { echo "Can't find $SKYDEX_DIR"; exit 1; }

USE_SERVICE=0
RESYNC=0
for arg in "$@"; do
  case "$arg" in
    --service) USE_SERVICE=1 ;;
    --resync)  RESYNC=1 ;;
    *) echo "Unknown option: $arg"; exit 1 ;;
  esac
done

echo "=========================================="
echo "  SkyDex — Fresh Start"
echo "=========================================="

# 1. Stop the running app/service so the DB file isn't locked.
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl stop skydex 2>/dev/null || true
fi
pkill -f "main.py" 2>/dev/null || true
sleep 1

# 2. Wipe the sightings DB (plus its WAL/SHM sidecars).
echo "Clearing tracking database..."
rm -f "$DB_DIR/skydex.db" "$DB_DIR/skydex.db-wal" "$DB_DIR/skydex.db-shm"
mkdir -p "$DB_DIR"

# 3. Reference DBs (FAA / OpenSky) — sync if missing, or always with --resync.
if [ "$RESYNC" -eq 1 ] || [ ! -f "$DB_DIR/faa_registry.db" ]; then
  echo "Syncing FAA registry (can take a few minutes)..."
  "$PY" sync_faa_db.py || echo "  (FAA sync failed — enrichment falls back to adsbdb)"
fi
if [ "$RESYNC" -eq 1 ] || [ ! -f "$DB_DIR/opensky_aircraft.db" ]; then
  echo "Syncing OpenSky aircraft DB..."
  "$PY" sync_opensky_db.py || echo "  (OpenSky DB sync failed — optional)"
fi
if [ "$RESYNC" -eq 1 ] || [ ! -f "$DB_DIR/airports.db" ]; then
  echo "Syncing airport database (OurAirports)..."
  "$PY" sync_airports_db.py || echo "  (airport sync failed — route codes will show without names)"
fi

# 4. Launch.
echo "Starting SkyDex..."
if [ "$USE_SERVICE" -eq 1 ] && command -v systemctl >/dev/null 2>&1; then
  sudo systemctl start skydex
  sudo systemctl restart skydex-kiosk 2>/dev/null || true
  echo "Services started. Live logs: journalctl -u skydex -f"
else
  echo "Running in the foreground (Ctrl+C to stop). Open http://localhost:8000"
  exec "$PY" main.py
fi
