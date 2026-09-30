"""Frozen bytes and hashes shared by Windows and Linux; no database required."""

import hashlib
import json
import math
from pathlib import Path

from xgtest.core.canonical import CanonicalCell, xgc1_encode
from xgtest.core.row_codec import decode_rows, encode_rows


def test_frozen_xgr1_and_xgc1_vectors():
    fixture = json.loads((Path(__file__).parent / "fixtures/row-codec-vectors-v1.json").read_text(encoding="utf-8"))
    rows = decode_rows(fixture["xgr1_rows"])
    assert encode_rows(rows) == fixture["xgr1_rows"]
    assert math.copysign(1, rows[0][4]) == -1
    assert math.isnan(rows[0][5]) and rows[0][10] == b"\x00\xff"
    types = fixture["xgc1_header"]["logical_types"]
    canonical = [[CanonicalCell(kind, value.isoformat() if kind in {"date", "timestamp_tz", "time"} else value) for kind, value in zip(types, row)] for row in rows]
    result = xgc1_encode(fixture["xgc1_header"], canonical)
    assert result.hex() == fixture["xgc1_hex"]
    assert hashlib.sha256(result).hexdigest() == fixture["xgc1_sha256"]
