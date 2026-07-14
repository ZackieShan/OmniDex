#!/usr/bin/env bash
# ============================================================================
# SkyDex backup -> local USB drive (nightly, everything).
#
# Backs up: dated DB snapshots (WAL-safe), settings.json, .env, the photo
# cache, and the reference DBs. rsync only copies NEW/changed photos, so after
# the first run the nightly cost is seconds.
#
# Target directory, first match wins:
#   1. $SKYDEX_BACKUP_DIR (if set)
#   2. /mnt/skydex-backup          (fstab mount — recommended, see below)
#   3. first mounted drive under /media/$USER/
#
# One-time USB setup (recommended so it survives reboots; see OPERATIONS.md):
#   lsblk -f                                   # find the stick, e.g. sda1 + UUID
#   sudo mkdir -p /mnt/skydex-backup
#   # ext4 stick:  UUID=xxxx  /mnt/skydex-backup ext4  nofail,noatime 0 2
#   # FAT32 stick: UUID=XXXX-XXXX /mnt/skydex-backup vfat nofail,noatime,uid=1000,gid=1000 0 2
#   sudo nano /etc/fstab   # add ONE line like the above
#   sudo systemctl daemon-reload && sudo mount -a
#
# Schedule: scripts/skydex-backup.timer (03:10 nightly). Manual: bash scripts/backup.sh
# Retention: 14 daily DB snapshots + 8 weekly (Sunday) copies.
# ============================================================================
set -u

command -v sqlite3 >/dev/null || { echo "sqlite3 not installed (sudo apt install sqlite3)"; exit 1; }

# --- find the backup drive ---------------------------------------------------
DEST="${SKYDEX_BACKUP_DIR:-}"
if [ -z "$DEST" ]; then
    if mountpoint -q /mnt/skydex-backup 2>/dev/null; then
        DEST="/mnt/skydex-backup"
    else
        DEST=$(find "/media/$(whoami)" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -1)
    fi
fi
[ -n "$DEST" ] && [ -d "$DEST" ] || { echo "!! no backup drive found — plug in the USB stick (or see setup notes in this script)"; exit 1; }
# refuse to "back up" onto the SD card if the mount silently fell off
if [ "$DEST" = "/mnt/skydex-backup" ] && ! mountpoint -q "$DEST"; then
    echo "!! /mnt/skydex-backup exists but nothing is mounted there"; exit 1
fi

DB="$HOME/.skydex/skydex.db"
[ -f "$DB" ] || { echo "no database at $DB"; exit 1; }

STAMP=$(date +%Y-%m-%d_%H%M)
DOW=$(date +%u)   # 1=Mon ... 7=Sun
mkdir -p "$DEST/daily" "$DEST/weekly" "$DEST/photos" "$DEST/reference"

# --- 1. database: consistent snapshot even while SkyDex runs (WAL-safe) ------
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
sqlite3 "$DB" ".backup '$WORK/skydex.db'" || { echo "sqlite snapshot failed"; exit 1; }
gzip -9 "$WORK/skydex.db"
cp "$WORK/skydex.db.gz" "$DEST/daily/skydex-$STAMP.db.gz"
echo "-- daily DB snapshot: $(du -h "$DEST/daily/skydex-$STAMP.db.gz" | cut -f1)"

# Sunday: keep a weekly copy too
[ "$DOW" = "7" ] && cp "$WORK/skydex.db.gz" "$DEST/weekly/skydex-$STAMP.db.gz" && echo "-- weekly copy kept"

# --- 2. settings + secrets ----------------------------------------------------
[ -f "$HOME/.skydex/settings.json" ] && cp -f "$HOME/.skydex/settings.json" "$DEST/settings.json"
[ -f "$HOME/skydex/.env" ] && cp -f "$HOME/skydex/.env" "$DEST/env.txt"

# --- 3. photos + reference DBs (rsync = only new/changed files) ---------------
if [ -d "$HOME/.skydex/photos" ]; then
    rsync -a --delete-excluded "$HOME/.skydex/photos/" "$DEST/photos/" 2>/dev/null \
        || cp -ru "$HOME/.skydex/photos/." "$DEST/photos/" 2>/dev/null || true
    echo "-- photos synced ($(du -sh "$DEST/photos" 2>/dev/null | cut -f1))"
fi
for refdb in faa_registry.db opensky_aircraft.db airports.db; do
    [ -f "$HOME/.skydex/$refdb" ] && cp -u "$HOME/.skydex/$refdb" "$DEST/reference/" 2>/dev/null || true
done

# --- 4. retention --------------------------------------------------------------
find "$DEST/daily"  -name 'skydex-*.db.gz' -mtime +14 -delete 2>/dev/null || true
find "$DEST/weekly" -name 'skydex-*.db.gz' -mtime +60 -delete 2>/dev/null || true

echo "-- backup complete -> $DEST  (free: $(df -h "$DEST" | awk 'NR==2{print $4}'))"

# ----------------------------------------------------------------------------
# RESTORE (after an SD card death):
#   sudo systemctl stop skydex
#   gunzip -c /mnt/skydex-backup/daily/skydex-<newest>.db.gz > ~/.skydex/skydex.db
#   cp /mnt/skydex-backup/settings.json ~/.skydex/  ;  cp /mnt/skydex-backup/env.txt ~/skydex/.env
#   cp -r /mnt/skydex-backup/photos ~/.skydex/photos
#   sudo systemctl start skydex
# ----------------------------------------------------------------------------
