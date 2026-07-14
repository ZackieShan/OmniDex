"""SkyDex voice — the kiosk speaks (offline TTS, Pokédex cadence).

Engine autodetect, best first:
  1. Piper (natural neural voices, runs realtime on a Pi 4):
       mkdir -p ~/piper && cd ~/piper
       wget https://github.com/rhasspy/piper/releases/latest/download/piper_linux_aarch64.tar.gz
       tar xf piper_linux_aarch64.tar.gz
       wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
       wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
  2. espeak-ng (robotic — honestly on-theme):  sudo apt install espeak-ng
  3. Neither installed -> announcements just log.

Announcements queue on a worker thread (never blocks a pipeline), rate-limit
themselves, respect quiet hours, and each category can be toggled in /admin.
"""

from __future__ import annotations

import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


def espeak_wav(voice: str, text: str) -> Optional[bytes]:
    """Synthesize a phrase in another LANGUAGE via espeak-ng (robot-accented,
    honestly on-theme) — powers the Guess the Language game. Returns WAV bytes."""
    import tempfile
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        return None
    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        subprocess.run([exe, "-v", voice, "-s", "135", "-w", path, text],
                       timeout=10, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass


PIPER_DIR = os.path.expanduser("~/piper")
PIPER_BIN = os.path.join(PIPER_DIR, "piper", "piper")
PIPER_BIN_ALT = os.path.join(PIPER_DIR, "piper")


def _find_piper():
    for p in (PIPER_BIN, PIPER_BIN_ALT):
        if os.path.isfile(p) and os.access(p, os.X_OK):
            model = next((os.path.join(PIPER_DIR, f) for f in os.listdir(PIPER_DIR)
                          if f.endswith(".onnx")), None)
            if model:
                return p, model
    return None, None


class VoiceAnnouncer:
    """say(text, category) -> spoken on the kiosk speaker, politely."""

    MIN_GAP = 8.0          # seconds between announcements (no chatterbox)

    def __init__(self):
        self._q: "queue.Queue[str]" = queue.Queue(maxsize=6)
        self._last_spoke = 0.0
        self._dedup = {}
        self._settings = None      # wired by main.py (settings module object)
        self.engine = "none"
        self._piper, self._model = _find_piper()
        if self._piper:
            self.engine = "piper"
        elif shutil.which("espeak-ng"):
            self.engine = "espeak"
        threading.Thread(target=self._worker, daemon=True, name="voice").start()
        logger.info("Voice engine: %s", self.engine)

    def wire_settings(self, settings_mod) -> None:
        self._settings = settings_mod

    # -- policy ---------------------------------------------------------------
    def _get(self, key, default):
        try:
            return self._settings.get(key) if self._settings else default
        except Exception:
            return default

    def _allowed(self, category: str) -> bool:
        if not self._get("voice_enabled", True) or self.engine == "none":
            return False
        hour = time.localtime().tm_hour
        start = int(self._get("voice_quiet_start_hour", 21))
        end = int(self._get("voice_quiet_end_hour", 8))
        quiet = (hour >= start or hour < end) if start > end else (start <= hour < end)
        if quiet:
            return False
        return bool(self._get(f"voice_{category}", True))

    # -- public ----------------------------------------------------------------
    def say(self, text: str, category: str = "air", dedup_key: str = "",
            dedup_seconds: float = 600) -> None:
        """Queue an announcement. dedup_key stops repeats (e.g. same aircraft).
        Also pushes to phones via ntfy (ignores quiet hours — pockets buzz
        silently) when a topic is configured."""
        if not text:
            return
        key = dedup_key or text
        now = time.time()
        if now - self._dedup.get(key, 0) < dedup_seconds:
            return
        if not bool(self._get(f"voice_{category}", True)):
            return
        self._dedup[key] = now
        self._push(text, category)
        if not self._allowed(category):
            return          # quiet hours / voice off — push already sent
        try:
            self._q.put_nowait((category, text))
        except queue.Full:
            pass    # busy skies > backlog of stale news

    def _push(self, text: str, category: str) -> None:
        topic = str(self._get("ntfy_topic", "")).strip()
        if not topic:
            return
        def _post():
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"https://ntfy.sh/{topic}", data=text.encode("utf-8"),
                    headers={"Title": f"SkyDex · {category.upper()}",
                             "User-Agent": "SkyDex/1.0"})
                urllib.request.urlopen(req, timeout=10).read()
            except Exception as e:
                logger.debug("ntfy push failed: %s", e)
        threading.Thread(target=_post, daemon=True).start()

    # -- worker ------------------------------------------------------------------
    def _worker(self) -> None:
        while True:
            item = self._q.get()
            category, text = item if isinstance(item, tuple) else ("air", item)
            wait = self.MIN_GAP - (time.time() - self._last_spoke)
            if wait > 0:
                time.sleep(wait)
            try:
                if self._get("voice_earcons", True):
                    self._earcon(category)
                self._speak(text)
            except Exception as e:
                logger.debug("voice failed: %s", e)
            self._last_spoke = time.time()

    # -- earcons: tiny synthesized chimes, one flavor per domain ---------------
    EARCON_DIR = os.path.expanduser("~/.skydex/earcons")
    # category -> list of (freq_hz, seconds) notes
    EARCON_NOTES = {
        "air":   [(660, 0.09), (990, 0.14)],            # ascending — look up
        "sea":   [(880, 0.22), (587, 0.26)],            # two-tone ship's bell
        "rail":  [(311, 0.16), (311, 0.16)],            # low double horn
        "iss":   [(1175, 0.08), (1568, 0.08), (2093, 0.12)],  # sparkle upward
        "storm": [(196, 0.25), (155, 0.3)],             # low rumble
    }

    def _earcon(self, category: str) -> None:
        notes = self.EARCON_NOTES.get(category)
        if not notes or self.engine == "none":
            return
        path = os.path.join(self.EARCON_DIR, f"{category}.wav")
        if not os.path.isfile(path):
            self._make_earcon(path, notes)
        subprocess.run(["aplay", "-q", path], timeout=6, stderr=subprocess.DEVNULL)

    @staticmethod
    def _make_earcon(path: str, notes) -> None:
        import math
        import struct
        import wave
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rate = 22050
        frames = bytearray()
        for freq, secs in notes:
            n = int(rate * secs)
            for i in range(n):
                fade = min(1.0, (n - i) / (rate * 0.04), i / (rate * 0.01))
                val = int(12000 * fade * math.sin(2 * math.pi * freq * i / rate))
                frames += struct.pack("<h", val)
            frames += b"\x00\x00" * int(rate * 0.03)    # tiny gap between notes
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(bytes(frames))

    def _speak(self, text: str) -> None:
        if self.engine == "piper":
            p1 = subprocess.Popen([self._piper, "--model", self._model, "--output_raw"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL)
            p2 = subprocess.Popen(["aplay", "-q", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
                                  stdin=p1.stdout, stderr=subprocess.DEVNULL)
            p1.stdin.write(text.encode("utf-8"))
            p1.stdin.close()
            p2.wait(timeout=30)
        elif self.engine == "espeak":
            subprocess.run(["espeak-ng", "-s", "150", "-p", "38", text],
                           timeout=30, stderr=subprocess.DEVNULL)
        else:
            logger.info("VOICE (no engine): %s", text)


class IssVoiceWatcher:
    """Announces 'the ISS rises in ten minutes' — checks the local SGP4
    predictor every few minutes; provider is a callable returning the pass
    predictor (api._sat) so we reuse its TLE cache."""

    def __init__(self, announcer: VoiceAnnouncer, provider, min_elevation_getter):
        self.announcer = announcer
        self.provider = provider
        self.min_el = min_elevation_getter
        threading.Thread(target=self._loop, daemon=True, name="iss-voice").start()

    def _loop(self) -> None:
        time.sleep(120)   # let the server settle first
        while True:
            try:
                sat = self.provider()
                if sat is not None:
                    data = sat.fetch(25544) or {}
                    now = time.time()
                    for p in data.get("passes", []):
                        lead = (p.get("start") or 0) - now
                        if 0 < lead <= 660 and (p.get("max_elevation") or 0) >= self.min_el():
                            mins = max(1, round(lead / 60))
                            self.announcer.say(
                                f"The International Space Station rises in {mins} minutes. "
                                f"Look up — it peaks at {round(p['max_elevation'])} degrees.",
                                category="iss", dedup_key=f"iss-{round(p['start'])}",
                                dedup_seconds=3600)
            except Exception as e:
                logger.debug("iss voice check failed: %s", e)
            time.sleep(240)


# Singleton — import `announcer` anywhere and .say().
announcer = VoiceAnnouncer()
