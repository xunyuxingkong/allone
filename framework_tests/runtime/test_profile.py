from xgtest.runtime.profile import build_profile


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
