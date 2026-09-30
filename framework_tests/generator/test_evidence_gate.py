"""Regressions for evidence that previously passed despite invalid content."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from xgtest.generator.evidence import validate_trial_artifact
from xgtest.generator.artifact_store import ArtifactRef, LocalArtifactStore
from xgtest.generator.lifecycle import _mutation_result_digest, record_candidate_mutation_evidence
from xgtest.core.canonical import xgmj1_sha256
from xgtest.query.loader import load_query_case
from xgtest.runtime.comparator import rows_semantic_sha256, rows_sha256


def _trial() -> dict:
    rows = [[1], [1], [None]]
    step = {
        "id": "q1", "status": "PASS", "columns": ["k"],
        "column_types": ["INTEGER"], "logical_types": ["int"],
        "row_count": len(rows), "result_rows": rows,
        "result_sha256": rows_sha256([tuple(row) for row in rows], ["INTEGER"], 1),
    }
    run = {"case_id": "QUERY.JOIN.TEST", "status": "PASS", "steps": [step]}
    from xgtest.core.canonical import xgmj1_sha256
    return {
        "case_id": "QUERY.JOIN.TEST", "semantic_hash": "a" * 64,
        "contract_set_id": "b" * 64, "runtime_profile_id": "c" * 64,
        "status": "PASS", "run1": copy.deepcopy(run), "run2": copy.deepcopy(run),
        "result_hash": xgmj1_sha256([run, run]),
    }


def _errors(artifact: dict) -> list[str]:
    return validate_trial_artifact(
        artifact, case_id="QUERY.JOIN.TEST", semantic_hash="a" * 64,
        step_ids=("q1",), contract_set_id="b" * 64,
        runtime_profile_id="c" * 64,
    )["errors"]


def test_valid_rows_and_duplicate_count_pass() -> None:
    assert _errors(_trial()) == []


@pytest.mark.parametrize("damage,expected", [
    ("failed_run", "RUN2_STATUS_OR_CASE_MISMATCH"),
    ("missing_rows", "RUN2_q1_RAW_ROWS_OR_METADATA_INVALID"),
    ("modified_rows", "RUN2_q1_RESULT_ROWS_HASH_MISMATCH"),
    ("wrong_count", "RUN2_q1_ROW_COUNT_MISMATCH"),
    ("missing_step", "RUN2_STEPS_MISMATCH"),
])
def test_trial_content_is_checked_even_when_outer_hash_rebound(damage: str, expected: str) -> None:
    artifact = _trial()
    run = artifact["run2"]
    if damage == "failed_run":
        run["status"] = "FAIL"
    elif damage == "missing_rows":
        run["steps"][0].pop("result_rows")
    elif damage == "modified_rows":
        run["steps"][0]["result_rows"][0][0] = 9
    elif damage == "wrong_count":
        run["steps"][0]["row_count"] = 99
    else:
        run["steps"] = []
    from xgtest.core.canonical import xgmj1_sha256
    artifact["result_hash"] = xgmj1_sha256([artifact["run1"], artifact["run2"]])
    assert expected in _errors(artifact)


def test_malformed_trial_reports_structured_failure() -> None:
    artifact = _trial()
    artifact["run2"] = []
    assert "RUN2_REPORT_INVALID" in _errors(artifact)


def test_rowsort_semantics_preserve_duplicates_but_ignore_order() -> None:
    first = [(1,), (1,), (None,)]
    reordered = [(None,), (1,), (1,)]
    missing_duplicate = [(None,), (1,)]
    kwargs = {"column_types": ["INTEGER"], "column_count": 1, "mode": "rowsort"}
    assert rows_semantic_sha256(first, **kwargs) == rows_semantic_sha256(reordered, **kwargs)
    assert rows_semantic_sha256(first, **kwargs) != rows_semantic_sha256(missing_duplicate, **kwargs)
    assert rows_semantic_sha256(first, mode="exact", column_types=["INTEGER"], column_count=1) != rows_semantic_sha256(reordered, mode="exact", column_types=["INTEGER"], column_count=1)


def test_trial_rowsort_accepts_reordered_double_run_with_valid_physical_hashes() -> None:
    artifact = _trial()
    rows = list(reversed(artifact["run2"]["steps"][0]["result_rows"]))
    artifact["run2"]["steps"][0]["result_rows"] = rows
    artifact["run2"]["steps"][0]["result_sha256"] = rows_sha256([tuple(row) for row in rows], ["INTEGER"], 1)
    from xgtest.core.canonical import xgmj1_sha256
    artifact["result_hash"] = xgmj1_sha256([artifact["run1"], artifact["run2"]])
    result = validate_trial_artifact(
        artifact, case_id="QUERY.JOIN.TEST", semantic_hash="a" * 64,
        step_ids=("q1",), step_modes={"q1": "rowsort"},
        contract_set_id="b" * 64, runtime_profile_id="c" * 64,
    )
    assert result["errors"] == []


def test_artifact_store_is_immutable_and_rejects_escape(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path / "evidence")
    first = store.put(b'{"result":1}\n')
    assert store.put(b'{"result":1}\n') == first
    second = store.put(b'{"result":2}\n')
    assert second.uri != first.uri
    assert store.get(first) == b'{"result":1}\n'
    with pytest.raises(ValueError, match="OUTSIDE_STORE"):
        store.get(ArtifactRef("../outside.json", first.sha256, first.size_bytes, first.media_type))
    (tmp_path / "evidence" / first.uri).write_bytes(b"changed")
    with pytest.raises(ValueError, match="ARTIFACT_HASH_MISMATCH"):
        store.get(first)


def _draft_candidate(tmp_path: Path, *, applicable: bool) -> Path:
    root = Path(__file__).resolve().parents[2]
    source = next(
        path for path in sorted((root / "candidates" / "query" / "join").glob("*.yaml"))
        if (yaml.safe_load(path.read_text(encoding="utf-8"))["coverage"][0]["assignment"]["predicate"] == "less_equal") == applicable
    )
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    payload["metadata"]["status"] = "draft"
    destination = tmp_path / source.name
    destination.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return destination


@pytest.mark.parametrize("applicable,result,expected", [
    (True, {"case_id": "FOREIGN.CASE", "mutation_id": "replace_le_with_lt", "status": "KILLED", "original_hash": "a" * 64, "mutated_hash": "b" * 64}, "CASE_ID_MISMATCH"),
    (True, {"mutation_id": "replace_le_with_lt", "status": "KILLED"}, "MUTATION_KILLED_HASHES_REQUIRED"),
    (False, {"mutation_id": "replace_le_with_lt", "status": "KILLED", "original_hash": "a" * 64, "mutated_hash": "b" * 64}, "APPLICABILITY_MISMATCH"),
    (False, {"mutation_id": "unknown", "status": "NOT_APPLICABLE"}, "ID_UNSUPPORTED"),
])
def test_mutation_writer_rejects_invalid_result_before_disk(
    tmp_path: Path, applicable: bool, result: dict, expected: str,
) -> None:
    candidate = _draft_candidate(tmp_path, applicable=applicable)
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    result = {"case_id": payload["metadata"]["id"], **result}
    artifact_root = tmp_path / "mutation-artifacts"
    with pytest.raises(ValueError, match=expected):
        record_candidate_mutation_evidence(candidate, result, artifact_root, {"sql_runtime_profile_id": "c" * 64})
    assert not artifact_root.exists()


def test_mutation_writer_rechecks_four_raw_executions(tmp_path: Path) -> None:
    candidate = _draft_candidate(tmp_path, applicable=True)
    case = load_query_case(candidate)

    def report(value: int) -> dict:
        rows = [[value]]
        return {
            "case_id": case.metadata.id, "status": "PASS",
            "steps": [{"id": "q1", "status": "PASS", "columns": ["k"], "column_types": ["INTEGER"],
                       "logical_types": ["int"], "row_count": 1, "result_rows": rows,
                       "result_sha256": rows_sha256([(value,)], ["INTEGER"], 1)}],
        }

    baseline = [report(1), report(1)]
    mutated = [report(2), report(2)]
    original_hash = _mutation_result_digest(baseline[0], case, require_rows=True)
    mutated_hash = _mutation_result_digest(mutated[0], case, require_rows=True)
    execution = {
        "original_sql_sha256": xgmj1_sha256([step.sql for step in case.steps]),
        "mutated_sql_sha256": xgmj1_sha256([step.sql.replace("a.k <= b.k", "a.k < b.k") for step in case.steps]),
        "baseline_runs": baseline, "mutated_runs": mutated,
        "build_observations": [
            {"captured_at": "2026-09-30T00:00:00+00:00", "query": "SHOW build_time;", "raw_value": "build version"},
            {"captured_at": "2026-09-30T00:01:00+00:00", "query": "SHOW build_time;", "raw_value": "build version"},
        ],
    }
    result = {"case_id": case.metadata.id, "mutation_id": "replace_le_with_lt", "status": "KILLED",
              "original_hash": original_hash, "mutated_hash": mutated_hash, "execution": execution}
    profile = {"sql_runtime_profile_id": "c" * 64, "identity": {"target": {"db_build": "build", "database_version": "version"}}}
    execution["mutated_runs"][0]["steps"][0]["result_rows"] = [[3]]
    with pytest.raises(ValueError, match="MUTATION_EXECUTION_ROW_HASH_INVALID"):
        record_candidate_mutation_evidence(candidate, result, tmp_path / "bad-artifacts", profile)
    assert not (tmp_path / "bad-artifacts").exists()
    execution["mutated_runs"][0] = report(2)
    saved = record_candidate_mutation_evidence(candidate, result, tmp_path / "artifacts", profile)
    artifact = json.loads(Path(saved["mutation_artifact"]).read_text(encoding="utf-8"))
    assert len(artifact["execution"]["baseline_runs"]) == len(artifact["execution"]["mutated_runs"]) == 2
