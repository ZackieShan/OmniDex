"""Tests for the ACARS/VDL-2 datalink receiver (acars.py) — parsing both
decoder JSON formats, direction detection, matching, and the ring buffer."""

import json

from acars import AcarsReceiver, norm_flight, norm_reg


def _rx(**kw):
    # Never call start() in tests — feed datagrams directly.
    return AcarsReceiver(udp_port=0, **kw)


def _acarsdec(**over):
    d = {"timestamp": 1700000000.5, "freq": 131.550, "mode": "2",
         "label": "H1", "block_id": "2", "tail": ".N123AB",
         "flight": "UA1234", "text": "POS N41.1 W073.1 FL350"}
    d.update(over)
    return json.dumps(d).encode()

def _vdl2(**over):
    acars = {"reg": ".N456CD", "flight": "DL89", "label": "A6",
             "msg_text": "CLRD TO LAND RWY 6"}
    acars.update(over.pop("acars", {}))
    v = {"t": {"sec": 1700000100, "usec": 1}, "freq": 136975000,
         "avlc": {"src": {"addr": "A1B2C3", "type": "Ground station"},
                  "dst": {"addr": "AC82EC", "type": "Aircraft"},
                  "acars": acars}}
    v.update(over)
    return json.dumps({"vdl2": v}).encode()


class TestNormalizers:
    def test_norm_reg(self):
        assert norm_reg(".N-123ab ") == "N123AB"
        assert norm_reg(None) == ""

    def test_norm_flight(self):
        assert norm_flight(" ua 1234 ") == "UA1234"


class TestAcarsdecParsing:
    def test_downlink_digit_block_id(self):
        rx = _rx()
        assert rx.feed(_acarsdec()) == 1
        m = rx.recent(1)[0]
        assert m["dir"] == "down" and m["source"] == "acars"
        assert m["reg"] == "N123AB" and m["flight"] == "UA1234"
        assert m["hex"] is None and m["ts"] == 1700000000.5

    def test_uplink_letter_block_id(self):
        rx = _rx()
        rx.feed(_acarsdec(block_id="A", text="LOADSHEET READY"))
        assert rx.recent(1)[0]["dir"] == "up"

    def test_empty_text_dropped(self):
        rx = _rx()
        assert rx.feed(_acarsdec(text="")) == 0
        assert rx.recent(5) == []


class TestVdl2Parsing:
    def test_uplink_carries_aircraft_hex_from_dst(self):
        rx = _rx()
        assert rx.feed(_vdl2()) == 1
        m = rx.recent(1)[0]
        assert m["dir"] == "up" and m["source"] == "vdl2"
        assert m["hex"] == "AC82EC" and m["reg"] == "N456CD"
        assert m["freq"] == 136.975

    def test_downlink_uses_src_addr(self):
        rx = _rx()
        rx.feed(_vdl2(avlc={"src": {"addr": "AC82EC", "type": "Aircraft"},
                            "dst": {"addr": "A1B2C3", "type": "Ground station"},
                            "acars": {"reg": ".N456CD", "flight": "DL89",
                                      "label": "H1", "msg_text": "OUT 1432Z"}}))
        m = rx.recent(1)[0]
        assert m["dir"] == "down" and m["hex"] == "AC82EC"


class TestBufferAndMatching:
    def test_garbage_and_multiline_datagrams(self):
        rx = _rx()
        blob = b"not json\n" + _acarsdec() + b"\n" + _vdl2() + b"\n\n"
        assert rx.feed(blob) == 2
        assert rx.stats["messages"] == 2

    def test_ring_buffer_caps(self):
        rx = _rx(max_messages=3)
        for i in range(5):
            rx.feed(_acarsdec(text=f"MSG {i}"))
        texts = [m["text"] for m in rx.recent(10)]
        assert texts == ["MSG 4", "MSG 3", "MSG 2"]  # newest first, capped

    def test_for_aircraft_matches_hex_reg_flight_chat_order(self):
        rx = _rx()
        rx.feed(_acarsdec())                       # reg N123AB, flight UA1234
        rx.feed(_vdl2())                           # hex AC82EC, reg N456CD
        rx.feed(_acarsdec(tail=".N999ZZ", flight="WN1"))
        assert len(rx.for_aircraft(reg="n-123ab")) == 1
        assert len(rx.for_aircraft(hex_code="ac82ec")) == 1
        assert len(rx.for_aircraft(flight="ua 1234")) == 1
        assert rx.for_aircraft(reg="N000XX") == []
        # chat order = oldest first
        rx.feed(_acarsdec(text="SECOND", timestamp=1700000002.0))
        msgs = rx.for_aircraft(reg="N123AB")
        assert [m["text"] for m in msgs][-1] == "SECOND"
