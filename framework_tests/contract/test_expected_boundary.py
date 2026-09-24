"""The four Expected variants must remain disjoint at the asset boundary."""

import pytest
from pydantic import ValidationError

from xgtest.core.models import ExpectedError, ExpectedRows, decode_expected


@pytest.mark.parametrize("payload", [
    {},
    {"rows": [], "sha256": "a" * 64},
    {"code": "E1001", "rows": [[1]]},
    {"affected_rows": -1},
    {"message_pattern": ""},
    {"code": ""},
    {"sqlstate": ""},
    {"rows": "not-a-row-list"},
    {"rows": [[1]], "unknown": True},
])
def test_invalid_or_mixed_expected_is_rejected(payload) -> None:
    with pytest.raises((ValueError, ValidationError)):
        decode_expected(payload)


def test_zero_rows_and_one_zero_column_row_are_distinct() -> None:
    zero_rows = decode_expected({"rows": []})
    one_empty_row = decode_expected({"rows": [[]]})
    assert isinstance(zero_rows, ExpectedRows)
    assert zero_rows.rows == ()
    assert one_empty_row.rows == ((),)


def test_error_variant_is_explicit() -> None:
    assert isinstance(decode_expected({"code": "E5021"}), ExpectedError)
