import hashlib

import pytest

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
