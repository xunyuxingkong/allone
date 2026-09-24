"""Versioned semantic identity vectors for Runtime Profile v0.2."""

from copy import deepcopy

import pytest

from xgtest.runtime.profile import build_profile


BASE_EVIDENCE = {
    "contract_set_id": "a" * 64,
    "target": {
        "database_product": "xugu", "database_version": "7", "db_build": "build-1",
        "os": "linux", "arch": "x86_64", "mode": "default",
        "configuration_fingerprint": "b" * 64,
        "host_hash": "host-a", "database_alias": "SYSTEM",
    },
    "driver": {"module": "xgcondb", "version": [2, 3, 9]},
    "capabilities": {
        "type_mapping": {"decimal": {"mapping_status": "LOSSY", "canonical_compatibility": "FAILED"}},
        "transaction_commit_rollback": {
            "status": "VERIFIED", "autocommit_disabled": True,
            "commit_visible_count": 1, "rollback_visible_count": 0,
        },
        "sql_error_mapping": {"status": "VERIFIED", "code": "E5021", "message": "table XGT_A missing"},
        "cancel_stop_proof": {"status": "UNKNOWN", "driver_has_cancel": False},
        "reset_probe": {"status": "UNKNOWN"},
    },
}

# Fixed after the v0.2 projection is reviewed. Changing this value requires
# a contract version decision rather than silently updating the assertion.
BASE_PROFILE_ID = "3a4fcf68668615743c5d4303c814ff79277dc82bec8096ac41117f35e3644cea"


@pytest.mark.parametrize("path,value", [
    (("started_at",), "2026-09-17T00:00:00Z"),
    (("finished_at",), "2026-09-17T00:01:00Z"),
    (("probe_run_id",), "run-random-1"),
    (("artifact",), "/tmp/probe-1.json"),
    (("duration_ms",), 501),
    (("target", "host_hash"), "host-b"),
    (("target", "database_alias"), "OTHER"),
    (("target", "host"), "192.0.2.1"),
    (("capabilities", "sql_error_mapping", "message"), "table XGT_B missing"),
    (("capabilities", "sql_error_mapping", "server_pid"), 1234),
    (("capabilities", "connection", "session_id"), "session-2"),
    (("capabilities", "type_mapping", "decimal", "observed"), {"repr": "random"}),
])
def test_runtime_noise_does_not_change_identity(path, value) -> None:
    evidence = deepcopy(BASE_EVIDENCE)
    node = evidence
    for key in path[:-1]:
        node = node.setdefault(key, {})
    node[path[-1]] = value
    assert build_profile(evidence)["sql_runtime_profile_id"] == BASE_PROFILE_ID


@pytest.mark.parametrize("path,value", [
    (("target", "database_product"), "other"),
    (("target", "database_version"), "8"),
    (("target", "db_build"), "build-2"),
    (("target", "os"), "windows"),
    (("target", "arch"), "aarch64"),
    (("target", "mode"), "compat"),
    (("target", "configuration_fingerprint"), "c" * 64),
    (("driver", "version"), [2, 3, 10]),
    (("capabilities", "type_mapping", "decimal", "mapping_status"), "EXACT"),
    (("capabilities", "transaction_commit_rollback", "rollback_visible_count"), 1),
    (("capabilities", "sql_error_mapping", "code"), "E5022"),
    (("capabilities", "cancel_stop_proof", "driver_has_cancel"), True),
    (("capabilities", "reset_probe", "status"), "VERIFIED"),
    (("contract_set_id",), "d" * 64),
])
def test_semantic_change_changes_identity(path, value) -> None:
    evidence = deepcopy(BASE_EVIDENCE)
    node = evidence
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert build_profile(evidence)["sql_runtime_profile_id"] != BASE_PROFILE_ID


def test_baseline_profile_id_is_frozen() -> None:
    assert build_profile(BASE_EVIDENCE)["sql_runtime_profile_id"] == BASE_PROFILE_ID
