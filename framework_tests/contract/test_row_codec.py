import json
import math
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest

from xgtest.core.row_codec import decode_cell, decode_rows, encode_rows
from xgtest.core.models import QueryStepReport
from xgtest.generated.registry_enums import StepStatus
from xgtest.runtime.comparator import rows_sha256


def test_xgr1_roundtrip_retains_exact_driver_types_and_values():
    rows = ((None, True, 2**63 - 1, "中文", b"\x00\xff", Decimal("1.2300"), date(2020, 1, 2), time(12, 3, 4, 123456), datetime(2020, 1, 2, 3, tzinfo=timezone.utc)),)
    restored = decode_rows(json.loads(json.dumps(encode_rows(rows), ensure_ascii=False)))
    assert restored == rows
    assert [type(cell) for cell in restored[0]] == [type(cell) for cell in rows[0]]
    assert restored[0][5].as_tuple() == rows[0][5].as_tuple()


def test_raw_report_roundtrip_preserves_blob_and_xgc1_hash():
    rows = ((b"\x00\xff", date(2020, 1, 2), None),)
    types = ("BLOB", "DATE", "INTEGER")
    digest = rows_sha256(list(rows), types, 3)
    report = QueryStepReport(id="q1", status=StepStatus.PASS, duration_ms=0, columns=("b", "d", "n"), column_types=types, result_rows=rows, row_count=1, result_sha256=digest)
    restored = QueryStepReport.model_validate_json(report.model_dump_json())
    assert restored.result_rows == rows
    assert rows_sha256(list(restored.result_rows), types, 3) == digest


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_nonfinite_float_has_explicit_json_tag(value):
    encoded = encode_rows(((value,),))
    serialized = json.dumps(encoded, allow_nan=False)
    restored = decode_rows(json.loads(serialized))[0][0]
    assert math.isnan(restored) if math.isnan(value) else restored == value


@pytest.mark.parametrize("value", [{"$xgr1": "unknown", "value": "x"}, {"$xgr1": "bytes", "value": "!"}, {"$xgr1": "date", "value": "bad"}, {"value": "x"}])
def test_invalid_typed_cell_fails_closed(value):
    with pytest.raises(ValueError):
        decode_cell(value)
