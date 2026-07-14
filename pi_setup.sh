#!/bin/bash
# SkyDex Raspberry Pi Setup Script
# Run this on your Pi to install dependencies, build readsb, and set up auto-start
#
# Usage:
#   cd ~/skydex
#   chmod +x pi_setup.sh
#   ./pi_setup.sh

set -e

SKYDEX_DIR="$HOME/skydex"
DB_DIR="$HOME/.skydex"
echo "=========================================="
echo "  SkyDex Raspberry Pi Setup"
echo "=========================================="

# ----------------------------------------------------------------------------
# 1. System dependencies
# ----------------------------------------------------------------------------
echo ""
echo "[1/7] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-fastapi python3-uvicorn python3-jinja2 python3-aiohttp \
    libzstd-dev build-essential git cmake rtl-sdr \
    fonts-noto-color-emoji \
    chromium-browser || sudo apt-get install -y chromium

# fonts-noto-color-emoji is REQUIRED for the aircraft type icons and the
# speaker/mute icon to render — without an emoji font Chromium shows blank
# boxes ("tofu") instead of the SkyDex icons.
sudo fc-cache -f >/dev/null 2>&1 || true

# Verify chromium binary
if [ -f /usr/bin/chromium ]; then
    CHROME_BIN="/usr/bin/chromium"
elif [ -f /usr/bin/chromium-browser ]; then
    CHROME_BIN="/usr/bin/chromium-browser"
else
    echo "WARNING: Chromium binary not found. Kiosk mode may fail."
    CHROME_BIN="chromium"
fi
echo "Chromium binary: $CHROME_BIN"

# ----------------------------------------------------------------------------
# 2. Install readsb (decoder) via the maintained wiedehopf installer
# ----------------------------------------------------------------------------
echo ""
echo "[2/7] Installing readsb (RTL-SDR ADS-B decoder)..."
# This auto-detects the RTL-SDR, installs + enables the readsb service, and
# uses adaptive gain. (Standard community installer; needs internet.)
sudo bash -c "$(wget -nv -O - https://github.com/wiedehopf/adsb-scripts/raw/master/readsb-install.sh)" || \
    echo "WARNING: readsb install failed — SkyDex will use the OpenSky fallback."

# Set your receiver location (right-click your house in Google Maps and put
# YOUR coordinates here — the default below is the KBDR airfield).
sudo readsb-set-location 41.1635 -73.1262 2>/dev/null || true
echo "readsb installed."

# ----------------------------------------------------------------------------
# 3. Install tar1090 (serves aircraft.json that SkyDex reads)
# ----------------------------------------------------------------------------
echo ""
echo "[3/7] Installing tar1090 web feed..."
# tar1090 serves the live JSON at http://localhost/tar1090/data/aircraft.json,
# which SkyDex auto-detects. It also gives you a full map UI at /tar1090.
sudo bash -c "$(wget -nv -O - https://github.com/wiedehopf/tar1090/raw/master/install.sh)" || \
    echo "WARNING: tar1090 install failed — check internet / try again."
echo "tar1090 installed (SkyDex reads localhost/tar1090/data/aircraft.json)."

# ----------------------------------------------------------------------------
# 4. Create database directory
# ----------------------------------------------------------------------------
echo ""
echo "[4/7] Setting up database directory..."
mkdir -p "$DB_DIR"

# ----------------------------------------------------------------------------
# 5. Install SkyDex systemd service
# ----------------------------------------------------------------------------
echo ""
echo "[5/7] Installing SkyDex systemd service..."

cat << EOF | sudo tee /etc/systemd/system/skydex.service
[Unit]
Description=SkyDex Aircraft Tracker
After=network-online.target readsb.service
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SKYDEX_DIR
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=:0
ExecStart=/usr/bin/python3 $SKYDEX_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable skydex.service
echo "SkyDex service installed."

# ----------------------------------------------------------------------------
# 6. Install Chromium kiosk systemd service
# ----------------------------------------------------------------------------
echo ""
echo "[6/7] Installing Chromium kiosk service..."

cat << EOF | sudo tee /etc/systemd/system/skydex-kiosk.service
[Unit]
Description=SkyDex Chromium Kiosk
After=skydex.service
Wants=skydex.service

[Service]
Type=simple
User=$USER
Environment=DISPLAY=:0
Environment=XDG_SESSION_TYPE=x11
ExecStartPre=/bin/sleep 15
ExecStart=$CHROME_BIN --kiosk --app=http://localhost:8000 \\
    --no-sandbox --disable-gpu \\
    --disable-dev-shm-usage --disable-web-security \\
    --window-size=1024,600 --window-position=0,0 \\
    --disable-infobars --disable-features=TranslateUI \\
    --no-first-run --no-default-browser-check \\
    --disable-background-networking --disable-sync \\
    --password-store=basic --autoplay-policy=no-user-gesture-required \\
    --touch-events=enabled --disable-pinch --overscroll-history-navigation=0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable skydex-kiosk.service
echo "Kiosk service installed."

# ----------------------------------------------------------------------------
# 7. Start services
# ----------------------------------------------------------------------------
echo ""
echo "[7/7] Starting services..."
sudo systemctl restart readsb || true
sudo systemctl start skydex.service
sudo systemctl start skydex-kiosk.service || true

echo ""
echo "=========================================="
echo "  SkyDex Setup Complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  readsb:        sudo systemctl status readsb"
echo "  skydex:        sudo systemctl status skydex"
echo "  kiosk:         sudo systemctl status skydex-kiosk"
echo ""
echo "Logs:"
echo "  SkyDex:        journalctl -u skydex -f"
echo "  readsb:        journalctl -u readsb -f"
echo "  Local log:     tail -f /tmp/skydex.log"
echo ""
echo "Database:        $DB_DIR/skydex.db"
echo "Web UI:          http://localhost:8000"
echo ""
echo "To clear the database and start fresh:"
echo "  rm $DB_DIR/skydex.db"
echo "  sudo systemctl restart skydex"
echo ""
