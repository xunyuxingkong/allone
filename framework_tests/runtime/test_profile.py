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
