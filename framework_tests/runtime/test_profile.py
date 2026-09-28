import hashlib

import pytest

from xgtest.core.models import RuntimeProfile
from xgtest.runtime.profile import build_profile, validate_profile


def test_profile_is_stable_and_omits_unapproved_target_fields() -> None:
    evidence = {
        "target": {"host_hash": "abc", "database_alias": "SYSTEM", "port": "1907"},
        "driver": {"version": [2, 3, 9]},
        "capabilities": {"connection": {"status": "VERIFIED"}},
    }
    profile = build_profile(evidence)
    assert profile == build_profile(evidence)
    assert profile["target"] == {"database_alias": "SYSTEM", "host_hash": "abc"}
    assert len(profile["sql_runtime_profile_id"]) == 64


def test_profile_rejects_target_or_driver_drift() -> None:
    profile = build_profile({"target": {"host_hash": hashlib.sha256(b"host").hexdigest(), "database_alias": "SYSTEM"}, "driver": {"version": [2, 3, 9]}})
    validate_profile(profile, host="host", database="SYSTEM", driver_version=(2, 3, 9))
    with pytest.raises(ValueError, match="RUNTIME_PROFILE_MISMATCH"):
        validate_profile(profile, host="other", database="SYSTEM", driver_version=(2, 3, 9))


def test_profile_can_be_bound_to_contract_set() -> None:
    profile = build_profile({
        "target": {"host_hash": hashlib.sha256(b"host").hexdigest(), "database_alias": "SYSTEM"},
        "driver": {"version": [2, 3, 9]},
        "contract_set_id": "a" * 64,
    })
    validate_profile(
        profile,
        host="host",
        database="SYSTEM",
        driver_version=(2, 3, 9),
        contract_set_id="a" * 64,
    )
    with pytest.raises(ValueError, match="contract set differs"):
        validate_profile(
            profile,
            host="host",
            database="SYSTEM",
            driver_version=(2, 3, 9),
            contract_set_id="b" * 64,
        )


def test_profile_id_excludes_probe_run_context() -> None:
    first = build_profile({
        "target": {"host_hash": "host-a", "database_alias": "SYSTEM", "db_build": "b1"},
        "driver": {"version": [2, 3, 9]},
        "capabilities": {"connection": {"status": "VERIFIED", "started_at": "t1", "table_name": "T1"}},
        "started_at": "t1",
    })
    second = build_profile({
        "target": {"host_hash": "host-b", "database_alias": "SYSTEM", "db_build": "b1"},
        "driver": {"version": [2, 3, 9]},
        "capabilities": {"connection": {"status": "VERIFIED", "started_at": "t2", "table_name": "T2"}},
        "started_at": "t2",
    })
    assert first["sql_runtime_profile_id"] == second["sql_runtime_profile_id"]


def test_profile_id_excludes_random_error_message_details() -> None:
    base = {
        "target": {"host_hash": "host-a", "database_alias": "SYSTEM", "db_build": "b1"},
        "driver": {"version": [2, 3, 9]},
        "capabilities": {"sql_error_mapping": {
            "status": "VERIFIED", "exception_type": "OperationalError",
            "message": "[E5021] table XGT_CAP_A123_MISSING does not exist",
        }},
    }
    changed = {**base, "capabilities": {"sql_error_mapping": {
        "status": "VERIFIED", "exception_type": "OperationalError",
        "message": "[E5021] table XGT_CAP_B987_MISSING does not exist",
    }}}
    assert build_profile(base)["sql_runtime_profile_id"] == build_profile(changed)["sql_runtime_profile_id"]


def test_profile_identity_rejects_unregistered_nested_fields() -> None:
    profile = build_profile({
        "target": {"host_hash": "host-a", "database_alias": "SYSTEM"},
        "driver": {"version": [2, 3, 9]},
        "capabilities": {"connection": {"status": "VERIFIED"}},
    })
    profile["identity"]["driver"]["host"] = "should-not-be-semantic"
    with pytest.raises(ValueError, match="extra"):
        RuntimeProfile.model_validate(profile)


def test_logical_type_is_part_of_runtime_mapping_identity() -> None:
    base = {
        "target": {"host_hash": "host", "database_alias": "SYSTEM"},
        "driver": {"version": [2, 3, 9]},
        "capabilities": {"type_mapping": {"integer": {
            "logical_type": "int",
            "mapping_fidelity": "EXACT",
            "canonical_encoding": "VERIFIED",
            "support_status": "SUPPORTED",
        }}},
    }
    changed = {
        **base,
        "capabilities": {"type_mapping": {"integer": {
            **base["capabilities"]["type_mapping"]["integer"],
            "logical_type": "string",
        }}},
    }
    assert build_profile(base)["sql_runtime_profile_id"] != build_profile(changed)["sql_runtime_profile_id"]
