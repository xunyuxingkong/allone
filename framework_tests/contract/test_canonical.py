from decimal import Decimal
import math

import pytest

from xgtest.core.canonical import CanonicalCell, xgc1_encode, xgmj1_bytes, xgmj1_sha256


def test_xgmj1_documented_minimal_vector() -> None:
    value = {"z": Decimal("1.00"), "a": "中", "b": Decimal("-0")}
    expected = b'{"a":"\xe4\xb8\xad","b":0,"z":1}'
    assert xgmj1_bytes(value) == expected
    assert xgmj1_sha256(value) == "d7096f9172852751f9434e5208521cfb0d4ccda2ee58c7e1206a0ae5a6a18cef"


def test_xgmj1_rejects_float_and_escapes_control_codepoints() -> None:
    with pytest.raises(TypeError):
        xgmj1_bytes({"value": 1.0})
    assert xgmj1_bytes({"value": "a\nb"}) == b'{"value":"a\\u000ab"}'


def test_xgc1_frames_cells_and_preserves_logical_types() -> None:
    header = {
        "mode": "exact",
        "column_count": 2,
        "logical_types": ["int", "string"],
        "comparison_profile": "strict",
    }
    encoded = xgc1_encode(header, [[CanonicalCell("int", 7), CanonicalCell("string", "中")]])
    assert encoded.startswith(b"XGC1")
    assert b"\xe4\xb8\xad" in encoded
    with pytest.raises(ValueError):
        xgc1_encode(header, [[CanonicalCell("string", "7"), CanonicalCell("string", "x")]])


def test_xgc1_normalizes_decimal_nan_and_signed_zero() -> None:
    header = {"mode": "exact", "column_count": 3, "logical_types": ["decimal", "float", "float"], "comparison_profile": "strict"}
    first = xgc1_encode(header, [[CanonicalCell("decimal", Decimal("1.00")), CanonicalCell("float", -0.0), CanonicalCell("float", float("nan"))]])
    second = xgc1_encode(header, [[CanonicalCell("decimal", Decimal("1")), CanonicalCell("float", 0.0), CanonicalCell("float", math.nan)]])
    assert first == second


def test_xgc1_validates_temporal_format_and_bytes() -> None:
    header = {"mode": "exact", "column_count": 2, "logical_types": ["date", "bytes"], "comparison_profile": "strict"}
    assert xgc1_encode(header, [[CanonicalCell("date", "2026-09-15"), CanonicalCell("bytes", b"\x00\xff")]])
    with pytest.raises(ValueError, match="canonical format"):
        xgc1_encode(header, [[CanonicalCell("date", "yesterday"), CanonicalCell("bytes", b"")]])


def test_xgc1_rejects_invalid_temporal_values() -> None:
    date_header = {"mode": "exact", "column_count": 1, "logical_types": ["date"], "comparison_profile": "strict"}
    time_header = {"mode": "exact", "column_count": 1, "logical_types": ["time"], "comparison_profile": "strict"}
    with pytest.raises(ValueError, match="invalid temporal"):
        xgc1_encode(date_header, [[CanonicalCell("date", "2026-99-99")]])
    with pytest.raises(ValueError, match="invalid temporal"):
        xgc1_encode(time_header, [[CanonicalCell("time", "25:00:00")]])


def test_xgc1_covers_empty_duplicate_and_extreme_rows() -> None:
    empty_header = {"mode": "exact", "column_count": 0, "logical_types": [], "comparison_profile": "strict"}
    no_rows = xgc1_encode(empty_header, [])
    one_empty_row = xgc1_encode(empty_header, [()])
    assert no_rows != one_empty_row
    assert one_empty_row.startswith(b"XGC1")

    row_header = {"mode": "exact", "column_count": 2, "logical_types": ["int", "decimal"], "comparison_profile": "strict"}
    rows = [
        [CanonicalCell("int", 2**127), CanonicalCell("decimal", Decimal("1E+100"))],
        [CanonicalCell("int", 2**127), CanonicalCell("decimal", Decimal("1E+100"))],
    ]
    encoded = xgc1_encode(row_header, rows)
    assert encoded.count(b"XGC1") == 1
    assert encoded == xgc1_encode(row_header, rows)


def test_xgc1_distinguishes_timestamp_timezone_semantics() -> None:
    naive = {"mode": "exact", "column_count": 1, "logical_types": ["timestamp"], "comparison_profile": "strict"}
    aware = {"mode": "exact", "column_count": 1, "logical_types": ["timestamp_tz"], "comparison_profile": "strict"}
    naive_bytes = xgc1_encode(naive, [[CanonicalCell("timestamp", "2026-09-16T10:00:00")]])
    aware_bytes = xgc1_encode(aware, [[CanonicalCell("timestamp_tz", "2026-09-16T10:00:00+08:00")]])
    assert naive_bytes != aware_bytes
