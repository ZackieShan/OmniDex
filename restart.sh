#!/usr/bin/env bash
# ============================================================================
# SkyDex fresh restart — the "errno 98 never again" script.
#
#   cd ~/skydex && bash restart.sh
#
# Stops the service, kills every stray SkyDex process, forcibly frees port
# 8000, PROVES the port is free, then starts exactly one instance (the systemd
# service if installed, foreground python otherwise) and health-checks it.
#
# Use this for plain restarts. For deploying new code, use deploy.sh instead
# (it also syntax-checks the transfer and verifies the build).
# ============================================================================
set -u
cd "$(dirname "$0")"
PORT=8000

echo "== SkyDex restart $(date '+%H:%M:%S') =="

# --- 1. stop everything -----------------------------------------------------
echo "-- stopping service + killing strays"
sudo systemctl stop skydex 2>/dev/null || true
sudo pkill -9 -f 'python.*main\.py' 2>/dev/null || true
sudo pkill -9 -f uvicorn 2>/dev/null || true
sudo fuser -k ${PORT}/tcp 2>/dev/null || true
sleep 2

# --- 2. prove the port is actually free --------------------------------------
if sudo ss -ltnp | grep -q ":${PORT} "; then
    echo "!! PORT ${PORT} IS STILL BUSY — this is the squatter:"
    sudo ss -ltnp | grep ":${PORT} "
    echo "   Kill that PID by hand (sudo kill -9 <pid>) and rerun this script."
    exit 1
fi
echo "-- port ${PORT} is free"

# --- 3. start exactly ONE instance --------------------------------------------
if systemctl list-unit-files skydex.service --no-legend 2>/dev/null | grep -q skydex; then
    echo "-- starting skydex.service"
    sudo systemctl start skydex
    echo "-- waiting for the server"
    for i in $(seq 1 20); do
        sleep 1
        HEALTH=$(curl -s --max-time 2 "http://localhost:${PORT}/api/health" 2>/dev/null || true)
        if [ -n "$HEALTH" ]; then
            BUILD=$(echo "$HEALTH" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("version",{}).get("code_mtime_str","?"))' 2>/dev/null || echo "?")
            echo "-- UP. Running build: $BUILD"
            # Refresh the kiosk browser so it picks up the new ?v= cache-bust.
            if systemctl list-unit-files skydex-kiosk.service --no-legend 2>/dev/null | grep -q kiosk; then
                sudo systemctl restart skydex-kiosk 2>/dev/null \
                    && echo "-- kiosk browser refreshed" \
                    || echo "-- (kiosk restart failed — refresh the browser manually)"
            fi
            echo "== restart complete =="
            exit 0
        fi
    done
    echo "!! server did not come up — recent log:"
    sudo journalctl -u skydex -n 25 --no-pager
    exit 1
else
    echo "-- no skydex.service installed; starting in the FOREGROUND (Ctrl+C stops it)"
    echo "   (install the service later with: sudo cp scripts/skydex.service /etc/systemd/system/"
    echo "    && sudo systemctl daemon-reload && sudo systemctl enable --now skydex)"
    exec python3 main.py
fi
