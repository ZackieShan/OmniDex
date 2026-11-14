"""ACARS / VDL-2 datalink receiver — the planes' text messages.

Listens on a UDP port for JSON from the two standard open-source decoders and
keeps a rolling buffer of plane <-> ground messages, so the Dex detail page can
show a real "text thread" for an aircraft (downlinks from the plane, uplinks
from the ground station / controller).

Feed it with either (or both) decoders, each on its own RTL-SDR:

    # Classic ACARS on VHF (131.550 etc.) — acarsdec with JSON-over-UDP:
    acarsdec -o 0 -j 127.0.0.1:5555 -r <serial> 131.550 131.725 130.025 131.825

    # VDL Mode 2 on 136.975 — dumpvdl2 with JSON-over-UDP:
    dumpvdl2 --rtlsdr <serial> --output decoded:json:udp:address=127.0.0.1,port=5555 136975000

Both formats land on the same port; this module tells them apart. Messages
without any readable text (empty blocks, acks) are kept out of the buffer.

Direction convention used everywhere here:
    'down' = downlink, FROM the aircraft  (the green "sender" bubble)
    'up'   = uplink,   TO the aircraft    (the blue "response" bubble)

For plain acarsdec frames the ACARS block-id convention decides direction:
downlink block ids are digits 0-9, uplink block ids are letters. dumpvdl2
frames say it outright via the AVLC src/dst types — and, as a bonus, carry the
aircraft's ICAO hex address, which matches SkyDex's airframe keys directly.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def norm_reg(reg: Optional[str]) -> str:
    """Normalize a registration/tail for matching: 'N123AB', '.N-123ab' -> 'N123AB'."""
    return "".join(ch for ch in (reg or "").upper() if ch.isalnum())


def norm_flight(flight: Optional[str]) -> str:
    """Normalize a flight/callsign for matching: strip spaces, uppercase."""
    return "".join((flight or "").upper().split())


class AcarsReceiver:
    """Background UDP listener + rolling message store."""

    def __init__(self, udp_port: int = 5555, max_messages: int = 600):
        self.udp_port = int(udp_port)
        self._messages: deque = deque(maxlen=int(max_messages))
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.stats: Dict[str, Any] = {"datagrams": 0, "messages": 0, "last_msg_ts": None}

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, name="acars-udp", daemon=True)
        self._thread.start()
        logger.info("ACARS receiver listening for decoder JSON on UDP :%d", self.udp_port)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.udp_port))
            sock.settimeout(1.0)
        except OSError as e:
            logger.error("ACARS receiver could not bind UDP :%d: %s", self.udp_port, e)
            self._running = False
            return
        while self._running:
            try:
                data, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            self.stats["datagrams"] += 1
            self.feed(data)
        sock.close()

    # -- ingest --------------------------------------------------------------

    def feed(self, data: bytes) -> int:
        """Parse one datagram (possibly several newline-separated JSON objects).
        Returns how many displayable messages were stored. Public for tests."""
        stored = 0
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line.decode("utf-8", errors="replace"))
            except (ValueError, UnicodeDecodeError):
                continue
            msg = self._normalize(obj)
            if msg:
                with self._lock:
                    self._messages.append(msg)
                self.stats["messages"] += 1
                self.stats["last_msg_ts"] = msg["ts"]
                stored += 1
        return stored

    def _normalize(self, obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            if "vdl2" in obj:
                return self._from_vdl2(obj.get("vdl2") or {})
            if "text" in obj or "tail" in obj or "label" in obj:
                return self._from_acarsdec(obj)
        except Exception as e:  # malformed frame — never kill the listener
            logger.debug("ACARS frame dropped: %s", e)
        return None

    @staticmethod
    def _from_acarsdec(d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        text = str(d.get("text") or "").strip()
        if not text:
            return None
        block_id = str(d.get("block_id") or "")
        direction = "up" if block_id[:1].isalpha() else "down"
        return {
            "ts": float(d.get("timestamp") or time.time()),
            "hex": None,
            "reg": norm_reg(d.get("tail")),
            "reg_raw": str(d.get("tail") or "").lstrip(".").strip(),
            "flight": norm_flight(d.get("flight")),
            "label": str(d.get("label") or ""),
            "text": text,
            "dir": direction,
            "freq": d.get("freq"),
            "source": "acars",
        }

    @staticmethod
    def _from_vdl2(v: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        avlc = v.get("avlc") or {}
        acars = avlc.get("acars") or {}
        text = str(acars.get("msg_text") or "").strip()
        if not text:
            return None
        src = avlc.get("src") or {}
        dst = avlc.get("dst") or {}
        direction = "down" if "aircraft" in str(src.get("type") or "").lower() else "up"
        hex_addr = str((src if direction == "down" else dst).get("addr") or "").upper()
        t = v.get("t") or {}
        freq = v.get("freq")
        return {
            "ts": float(t.get("sec") or time.time()),
            "hex": hex_addr or None,
            "reg": norm_reg(acars.get("reg")),
            "reg_raw": str(acars.get("reg") or "").lstrip(".").strip(),
            "flight": norm_flight(acars.get("flight")),
            "label": str(acars.get("label") or ""),
            "text": text,
            "dir": direction,
            "freq": round(freq / 1e6, 3) if isinstance(freq, (int, float)) else freq,
            "source": "vdl2",
        }

    # -- queries -------------------------------------------------------------

    def recent(self, n: int = 30) -> List[Dict[str, Any]]:
        """Latest messages, newest first (for the firehose / health views)."""
        with self._lock:
            items = list(self._messages)
        return list(reversed(items))[: max(1, n)]

    def for_aircraft(self, hex_code: Optional[str] = None, reg: Optional[str] = None,
                     flight: Optional[str] = None, n: int = 40) -> List[Dict[str, Any]]:
        """Messages for one airframe, oldest first (chat order). Matches on the
        ICAO hex (VDL2 frames carry it), the registration, or the flight number."""
        hx = (hex_code or "").upper().strip()
        rg = norm_reg(reg)
        fl = norm_flight(flight)
        with self._lock:
            items = list(self._messages)
        out = [m for m in items if (hx and m.get("hex") == hx)
               or (rg and m.get("reg") == rg)
               or (fl and m.get("flight") == fl)]
        return out[-max(1, n):]


def match_to_contacts(msgs: List[Dict[str, Any]], contacts: Dict[str, Dict[str, Any]],
                      reg_of=None, limit: int = 12) -> List[Dict[str, Any]]:
    """Match datalink messages (newest first) to live receiver contacts, for the
    map's pop-up word bubbles. Returns at most one bubble per plane — its newest
    message — as {hex, dir, label, ts, text, callsign}.

    Matching order: ICAO hex (VDL2 carries it) > registration > flight number.
    `reg_of` is an optional callable hex -> registration (e.g. a Dex DB lookup),
    used to pair classic-ACARS tails with live ADS-B contacts.
    """
    by_hex: Dict[str, Any] = {}
    by_flt: Dict[str, Any] = {}
    by_reg: Dict[str, Any] = {}
    for hx, c in (contacts or {}).items():
        hxu = str(hx).upper()
        by_hex[hxu] = (hxu, c or {})
        f = norm_flight((c or {}).get("callsign"))
        if f:
            by_flt[f] = (hxu, c or {})
        r = norm_reg(reg_of(hxu)) if reg_of else ""
        if r:
            by_reg[r] = (hxu, c or {})
    out: List[Dict[str, Any]] = []
    used = set()
    for m in msgs:
        hit = (by_hex.get(m.get("hex") or "")
               or by_reg.get(m.get("reg") or "")
               or by_flt.get(m.get("flight") or ""))
        if not hit or hit[0] in used:
            continue
        hxu, c = hit
        used.add(hxu)
        out.append({"hex": hxu, "dir": m.get("dir"), "label": m.get("label"),
                    "ts": m.get("ts"), "text": (m.get("text") or "")[:140],
                    "callsign": c.get("callsign") or m.get("reg_raw") or ""})
        if len(out) >= max(1, limit):
            break
    return out
