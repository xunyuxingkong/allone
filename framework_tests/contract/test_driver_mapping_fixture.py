"""A real xgcondb 2.3.9 read-only metadata sample, not a type-name mock."""

import json
from pathlib import Path

from xgtest.adapter.xugu import map_driver_type
from xgtest.core.logical_types import classify_type_mapping, query_type_support


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "xugu_driver_type_mapping_v1.json"


def test_real_driver_metadata_mapping_has_no_silent_unknown_fallback() -> None:
    evidence = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert evidence["driver_version"] == [2, 3, 9]
    assert evidence["probe_mode"] == "read_only_expression"
    samples = {item["name"]: item for item in evidence["results"]}
    assert len(samples) == 22
    for item in samples.values():
        if item["status"] == "READ_ONLY_EXPRESSION":
            assert item["description_type_python_class"] == "builtins.str"
            assert map_driver_type(item["normalized_driver_type"]) == item["framework_logical_type"]
    assert samples["varbinary"]["status"] == "FAILED"
    assert samples["varbinary"]["error_code"] == "E19132"


def test_real_driver_semantic_limitations_remain_visible() -> None:
    samples = {item["name"]: item for item in json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]}
    for name in ("numeric", "decimal", "number", "datetime", "timestamp", "timestamp_tz"):
        assert samples[name]["canonical_compatibility"] == "FAILED"
    assert samples["timestamp_tz"]["normalized_driver_type"] == "DATETIME"
    for name in ("binary", "raw"):
        assert samples[name]["normalized_driver_type"] == "VARCHAR"
        assert samples[name]["framework_logical_type"] == "string"
    for name in ("int", "integer", "bigint", "smallint", "date", "time", "blob", "boolean"):
        assert samples[name]["canonical_compatibility"] == "VERIFIED"


def test_mapping_fidelity_is_separate_from_canonical_encoding() -> None:
    samples = {item["name"]: item for item in json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]}
    assert samples["binary"]["canonical_encoding"] == "VERIFIED"
    assert samples["binary"]["mapping_fidelity"] == "LOSSY"
    assert samples["binary"]["support_status"] == "UNSUPPORTED"
    assert samples["numeric"]["mapping_fidelity"] == "LOSSY"
    assert samples["timestamp_tz"]["mapping_fidelity"] == "AMBIGUOUS"
    assert samples["varbinary"]["mapping_fidelity"] == "UNKNOWN"
    assert all(samples[name]["support_status"] == "SUPPORTED" for name in (
        "int", "integer", "bigint", "smallint", "float", "double", "char", "varchar",
        "text", "date", "time", "blob", "boolean",
    ))
    assert query_type_support("NUMERIC")[1] is False
    assert query_type_support("VARCHAR(64)")[1] is True
    assert query_type_support(None)[1] is False


def test_type_mapping_classifier_preserves_two_independent_axes() -> None:
    outcome = classify_type_mapping("BINARY(8)", "VARCHAR", "builtins.str", "VERIFIED", "READ_ONLY_EXPRESSION")
    assert outcome == {
        "mapping_fidelity": "LOSSY",
        "canonical_encoding": "VERIFIED",
        "support_status": "UNSUPPORTED",
    }
