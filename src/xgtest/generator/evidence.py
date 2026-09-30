"""Read-only checks shared by trial acceptance and candidate promotion."""

from __future__ import annotations

from typing import Any

from xgtest.core.canonical import xgmj1_sha256
from xgtest.core.row_codec import decode_rows
from xgtest.runtime.comparator import rows_semantic_sha256, rows_sha256


def trial_projection(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": report["case_id"],
        "status": report["status"],
        "steps": [
            {
                "id": step["id"],
                "status": step["status"],
                "columns": step.get("columns", []),
                "column_types": step.get("column_types", []),
                "logical_types": step.get("logical_types", []),
                "row_count": step.get("row_count"),
                "result_rows": step.get("result_rows"),
                "result_sha256": step.get("result_sha256"),
            }
            for step in report["steps"]
        ],
    }


def validate_trial_artifact(
    artifact: dict[str, Any],
    *,
    case_id: str,
    semantic_hash: str,
    step_ids: tuple[str, ...],
    contract_set_id: str,
    runtime_profile_id: str,
    database_version: str | None = None,
    database_build_time: str | None = None,
    step_modes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Check the complete double trial, including rows against each step hash.

    Decode XGR1 cells before recomputing the runner's XGC1 digest.
    """
    errors: list[str] = []
    if artifact.get("case_id") != case_id or artifact.get("semantic_hash") != semantic_hash:
        errors.append("TRIAL_IDENTITY_MISMATCH")
    if artifact.get("contract_set_id") != contract_set_id:
        errors.append("TRIAL_CONTRACT_SET_MISMATCH")
    if artifact.get("runtime_profile_id") != runtime_profile_id:
        errors.append("TRIAL_RUNTIME_PROFILE_MISMATCH")
    if database_version is not None and artifact.get("database_version") != database_version:
        errors.append("TRIAL_DATABASE_VERSION_MISMATCH")
    if database_build_time is not None and artifact.get("database_build_time") != database_build_time:
        errors.append("TRIAL_DATABASE_BUILD_MISMATCH")
    if artifact.get("database_build_time") or database_build_time is not None:
        observations = artifact.get("build_observations")
        expected_build = f"{artifact.get('database_build_time', '')} {artifact.get('database_version', '')}".strip()
        if (
            not isinstance(observations, list)
            or len(observations) != 2
            or any(
                not isinstance(item, dict)
                or item.get("query") != "SHOW build_time;"
                or item.get("raw_value") != expected_build
                or not isinstance(item.get("captured_at"), str)
                for item in observations
            )
        ):
            errors.append("TRIAL_DATABASE_BUILD_OBSERVATION_MISSING_OR_STALE")
    if artifact.get("status") != "PASS":
        errors.append("TRIAL_STATUS_NOT_PASS")

    projections: list[dict[str, Any]] = []
    semantic_projections: list[dict[str, Any]] = []
    run_row_counts: dict[str, int] = {}
    for run_name in ("run1", "run2"):
        run = artifact.get(run_name)
        if not isinstance(run, dict):
            errors.append(f"{run_name.upper()}_REPORT_INVALID")
            continue
        if run.get("case_id") != case_id or run.get("status") != "PASS":
            errors.append(f"{run_name.upper()}_STATUS_OR_CASE_MISMATCH")
        steps = run.get("steps")
        if not isinstance(steps, list) or tuple(step.get("id") for step in steps if isinstance(step, dict)) != step_ids:
            errors.append(f"{run_name.upper()}_STEPS_MISMATCH")
            continue
        run_row_counts[run_name] = 0
        semantic_steps: list[dict[str, Any]] = []
        for step in steps:
            if not isinstance(step, dict):
                errors.append(f"{run_name.upper()}_STEP_INVALID")
                continue
            step_id = str(step.get("id", "<missing>"))
            prefix = f"{run_name.upper()}_{step_id}"
            if step.get("status") != "PASS":
                errors.append(f"{prefix}_STATUS_NOT_PASS")
            columns = step.get("columns")
            column_types = step.get("column_types")
            logical_types = step.get("logical_types")
            rows = step.get("result_rows")
            if (
                not isinstance(columns, list)
                or not isinstance(column_types, list)
                or not isinstance(logical_types, list)
                or len(columns) != len(column_types)
                or len(columns) != len(logical_types)
                or not isinstance(rows, list)
            ):
                errors.append(f"{prefix}_RAW_ROWS_OR_METADATA_INVALID")
                continue
            if not all(isinstance(row, list) and len(row) == len(columns) for row in rows):
                errors.append(f"{prefix}_ROW_WIDTH_MISMATCH")
                continue
            if step.get("row_count") != len(rows):
                errors.append(f"{prefix}_ROW_COUNT_MISMATCH")
            run_row_counts[run_name] += len(rows)
            try:
                decoded = decode_rows(rows)
                digest = rows_sha256(list(decoded), column_types, len(columns))
                semantic_digest = rows_semantic_sha256(
                    list(decoded), column_types, len(columns),
                    mode=(step_modes or {}).get(step_id, "exact"),
                )
            except (TypeError, ValueError, OverflowError):
                errors.append(f"{prefix}_RAW_ROWS_UNVERIFIABLE")
            else:
                if digest != step.get("result_sha256"):
                    errors.append(f"{prefix}_RESULT_ROWS_HASH_MISMATCH")
                semantic_steps.append({
                    "id": step_id, "status": step.get("status"),
                    "columns": columns, "column_types": column_types,
                    "logical_types": logical_types, "row_count": len(rows),
                    "semantic_result_sha256": semantic_digest,
                })
        try:
            projections.append(trial_projection(run))
        except (KeyError, TypeError):
            errors.append(f"{run_name.upper()}_PROJECTION_INVALID")
        semantic_projections.append({"case_id": run.get("case_id"), "status": run.get("status"), "steps": semantic_steps})

    trial_hash: str | None = None
    if len(projections) == 2:
        if len(semantic_projections) != 2 or semantic_projections[0] != semantic_projections[1]:
            errors.append("DOUBLE_RUN_RESULT_MISMATCH")
        trial_hash = xgmj1_sha256(projections)
        if artifact.get("result_hash") != trial_hash:
            errors.append("TRIAL_RESULT_HASH_MISMATCH")
    return {"errors": errors, "trial_hash": trial_hash, "run_row_counts": run_row_counts}
