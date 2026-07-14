# SkyDex Operations Guide

Everything you need to run, deploy, back up, and keep the kiosk alive for years.

## Daily workflow: deploying a change

1. Transfer the project folder to the Pi with Termius (replace `~/skydex`).
2. SSH in and run:
   ```bash
   cd ~/skydex && bash deploy.sh          # or: bash deploy.sh --test
   ```
   The script syntax-checks the transfer, restarts the service, verifies via
   `/api/health` that the running server matches the files you just sent, and
   refreshes the kiosk browser. If anything's wrong it says so and aborts.

One-time setup for password-less deploys:
```bash
echo 'skywatch ALL=NOPASSWD: /usr/bin/systemctl restart skydex, /usr/bin/systemctl restart skydex-kiosk' | sudo tee /etc/sudoers.d/skydex
```

**Golden rule:** only ONE thing launches SkyDex — the systemd service. Never
run `python3 main.py` while the service is running ("address already in use").
For foreground debugging: `sudo systemctl stop skydex` first.

## Services

```bash
sudo cp scripts/skydex.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now skydex
journalctl -u skydex -f          # live logs
```

## Backups (USB drive)

Nightly at 03:10 to the 32 GB USB stick: dated DB snapshots + settings + .env +
photo cache + reference DBs. Keeps 14 daily + 8 weekly DB copies; photos rsync
in place (only new files copy after the first run).

One-time setup — mount the stick at a fixed path so 3 AM backups always work:
```bash
sudo apt install sqlite3
lsblk -f                          # find the stick (e.g. sda1) and its UUID
sudo mkdir -p /mnt/skydex-backup
sudo nano /etc/fstab              # add ONE line (pick your filesystem):
  # ext4:   UUID=<uuid>  /mnt/skydex-backup  ext4  nofail,noatime  0  2
  # FAT32:  UUID=<UUID>  /mnt/skydex-backup  vfat  nofail,noatime,uid=1000,gid=1000  0  2
sudo systemctl daemon-reload && sudo mount -a
bash scripts/backup.sh            # test run
sudo cp scripts/skydex-backup.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now skydex-backup.timer
systemctl list-timers | grep skydex
```
Tip: an ext4-formatted stick is more reliable than FAT32 for this
(`sudo mkfs.ext4 -L SKYDEXBAK /dev/sda1` — wipes the stick, then use its new UUID).

If you skip the fstab step, the script falls back to whatever desktop-automounted
under `/media/skywatch/` — works, but only while the desktop session is running.

You can also trigger a backup from the admin page (`/admin` → Backup now).
Restore instructions are at the bottom of `scripts/backup.sh`.

## Admin page

`http://<pi-ip>:8000/admin` from any device on your network — status of every
feed, all runtime settings (radius, polling hours, night dim, attract mode,
LiveATC URL, retention), and action buttons (Restart, Backup now, Maintenance).
Settings live in `~/.skydex/settings.json` so folder-replace deploys never
touch them.

## Secrets

API keys live in `.env` in the project folder (transfers with it). Rotate a
key by editing `.env` and running `deploy.sh`. Keys are no longer in the code.

## SD-card longevity (recommended, one-time)

The two biggest SD-killers are journald and constant log writes:
```bash
# 1. Keep systemd journal in RAM (survivable loss; SkyDex state is in ~/.skydex)
sudo sed -i 's/^#\?Storage=.*/Storage=volatile/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald

# 2. Nightly DB maintenance is automatic (03:30, prunes raw telemetry >30 days,
#    checkpoints the WAL). Tune retention on the admin page.

# 3. Optional, gold standard: log2ram
sudo apt install log2ram
```

## Dongle pinning (udev)

Stops the ADS-B and AIS dongles from swapping identities after reboot/replug —
see `scripts/99-skydex-sdr.rules` (needs your two serials filled in).

## Remote access (phone on 5G, away from home)

The kiosk URLs only work on your home wifi. For everywhere-access, install
Tailscale — a free, zero-config VPN. No port forwarding, nothing exposed to
the public internet; only devices signed into YOUR account can connect.

```bash
# On the Pi (one time):
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up          # prints a login link — open it, sign in (Google works)
tailscale ip -4            # note the Pi's permanent 100.x.x.x address
```
Then install the Tailscale app on your phone (App Store / Play Store), sign in
with the same account, flip its toggle on, and from anywhere — 5G included:

- `http://100.x.x.x:8000` — the full kiosk
- `http://100.x.x.x:8000/admin` — the control panel
- Termius can SSH to `100.x.x.x` too, so you can even deploy from the beach.

With MagicDNS enabled (on by default in the Tailscale admin console) the
friendlier `http://raspberrypi:8000` works as well. Add either URL to your
phone's home screen and it behaves like an app.

**Do NOT port-forward 8000 on your router instead** — the kiosk and admin page
have no password (by design, LAN-trust), so exposing them publicly would let
anyone who finds your IP restart the app or change settings. Tailscale keeps
that trust model intact because the "network" is just your own devices.

## Health / troubleshooting

```bash
curl -s localhost:8000/api/health | python3 -m json.tool
```
- `version.code_mtime_str` — the build the server is actually running.
- `receiver.source_stats` — dump1090 vs OpenSky usage; `marine.aisstream.connected`.
- "address already in use" → something else owns :8000 → `sudo fuser -k 8000/tcp`
  then `sudo systemctl restart skydex`.
- "AISStream connected & subscribed" then silence = healthy, quiet water.
- Dongle "resource busy" → `sudo pkill -9 -f 'AIS-catcher|dump1090|rtl_'`, and
  the udev rule above prevents the kernel DVB driver from grabbing them.

## Tests

```bash
sudo apt install python3-pytest
cd ~/skydex && python3 -m pytest -q tests     # or: bash deploy.sh --test
```
The suite locks down the astronomy math (the sunrise bug!), the military
classifier, and vessel classification — the exact bugs we've actually hit.

## Voice + EtherDex setup (one time)

```bash
# Voice — Piper (natural) ; falls back to espeak-ng, else silent:
mkdir -p ~/piper && cd ~/piper
wget https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz
tar xf piper_linux_aarch64.tar.gz
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
sudo apt install espeak-ng          # the robotic fallback (optional but easy)
# Test after restart:  curl -X POST localhost:8000/api/admin/say -H 'Content-Type: application/json' -d '{"text":"SkyDex online."}'

# EtherDex — repurpose the old AIS dongle (SeaDex rides AISStream anyway):
sudo systemctl stop ais-catcher 2>/dev/null; sudo pkill -f AIS-catcher
sudo apt install rtl-433
rtl_433 -d "" | head            # smoke test — you should see JSON within minutes
# Antenna: collapse the telescopic whip to ~16.5 cm (433 MHz quarter-wave).
# If dongles swap, pin by serial in /admin -> Ether -> device selector (e.g. :00000102)
```
Voice toggles (per-category + quiet hours) and Ether settings live in /admin.
