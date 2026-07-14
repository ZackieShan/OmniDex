#!/usr/bin/env bash
# ============================================================================
# SkyDex deploy — run ON THE PI after replacing the folder over SFTP (Termius).
#
#   cd ~/skydex && bash deploy.sh          # normal deploy
#   cd ~/skydex && bash deploy.sh --test   # run the pytest suite first
#
# What it does: syntax-checks every Python file (catches a half-finished
# transfer), optionally runs tests, restarts the systemd service, then hits
# /api/health and PROVES the running server is serving the code you just
# uploaded (no more "restarted but still stale" mysteries).
#
# One-time setup so sudo doesn't prompt for a password:
#   echo 'skywatch ALL=NOPASSWD: /usr/bin/systemctl restart skydex, /usr/bin/systemctl restart skydex-kiosk' | \
#     sudo tee /etc/sudoers.d/skydex
# ============================================================================
set -u
cd "$(dirname "$0")"

PORT=8000
FAIL() { echo; echo "!! DEPLOY ABORTED: $1"; exit 1; }

echo "== SkyDex deploy $(date '+%H:%M:%S') =="

# 1. Syntax-check all Python (a truncated SFTP transfer shows up here, not at 3am)
echo "-- checking python syntax"
ERRS=0
for f in *.py; do
    python3 -m py_compile "$f" 2>/tmp/skydex_syntax || { echo "   SYNTAX ERROR in $f:"; cat /tmp/skydex_syntax; ERRS=1; }
done
[ "$ERRS" = "0" ] || FAIL "fix the syntax errors above and re-transfer"

# 2. Optional test run (needs: sudo apt install python3-pytest)
if [ "${1:-}" = "--test" ]; then
    if command -v pytest >/dev/null 2>&1 || python3 -m pytest --version >/dev/null 2>&1; then
        echo "-- running tests"
        python3 -m pytest -q tests || FAIL "tests failed"
    else
        echo "-- pytest not installed, skipping (sudo apt install python3-pytest)"
    fi
fi

# 3. Newest file we just transferred (the health check must match this)
NEWEST=$(find . -name '*.py' -newer /proc/1 -prune 2>/dev/null | head -1)
WANT=$(find . \( -name '*.py' -o -name '*.js' -o -name '*.css' -o -name '*.html' \) \
        -not -path './.git/*' -printf '%T@\n' 2>/dev/null | sort -n | tail -1 | cut -d. -f1)

# 4. Restart the service
echo "-- restarting skydex.service"
sudo systemctl restart skydex || FAIL "systemctl restart failed (is the service installed? see scripts/skydex.service)"

# 5. Wait for the server, then verify it's serving the new build
echo "-- waiting for server"
GOT=""
for i in $(seq 1 20); do
    sleep 1
    HEALTH=$(curl -s --max-time 2 "http://localhost:$PORT/api/health" 2>/dev/null || true)
    [ -n "$HEALTH" ] && { GOT=$(echo "$HEALTH" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("version",{}).get("code_mtime",0))' 2>/dev/null || echo 0); break; }
done
[ -n "$GOT" ] || { sudo journalctl -u skydex -n 25 --no-pager; FAIL "server did not come up on :$PORT (log above)"; }

if [ -n "$WANT" ] && [ "$GOT" -ge "$WANT" ] 2>/dev/null; then
    echo "-- OK: server is running the code you just uploaded (build $(date -d @"$GOT" '+%Y-%m-%d %H:%M:%S'))"
else
    echo "-- WARNING: server code_mtime=$GOT, newest transferred file=$WANT"
    echo "   (If these differ by more than a few seconds, the transfer may have gone to the wrong folder.)"
fi

# 6. Refresh the kiosk browser so it picks up new JS/CSS (?v= cache-bust)
if systemctl list-unit-files skydex-kiosk.service >/dev/null 2>&1; then
    echo "-- restarting kiosk browser"
    sudo systemctl restart skydex-kiosk 2>/dev/null || echo "   (kiosk restart failed — refresh the browser manually)"
fi

echo "== deploy complete =="
