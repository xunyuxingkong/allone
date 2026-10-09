"""Small safe projections for worker errors and regression failures."""
_KNOWN_CODES = {
    "DB_REQUEST_PATH_INVALID", "DB_REQUEST_CASE_ID_INVALID", "DB_OPERATION_UNSUPPORTED",
    "RUNTIME_PROFILE_REQUIRED_FOR_REGRESSION", "RUNTIME_PROFILE_DATABASE_BUILD_REQUIRED",
    "RUNTIME_PROFILE_MISMATCH", "DATABASE_BUILD_DRIFT", "DATABASE_BUILD_OBSERVATION_INVALID",
}


def safe_worker_error(error: Exception) -> dict:
    # Only known domain codes may leave the worker; driver messages are never copied.
    prefix = str(error).split(":", 1)[0]
    code = prefix if isinstance(error, ValueError) and prefix in _KNOWN_CODES else (
        "DATABASE_DRIVER_UNAVAILABLE" if isinstance(error, ImportError) else "DATABASE_EXECUTION_ERROR")
    return {"status": "BLOCKED", "error": code, "error_code": code,
            "error_type": "DriverUnavailable" if isinstance(error, ImportError) else "ExecutionError",
            "safe_message": "Database operation could not complete; check runtime configuration and the referenced execution artifacts."}


def failure_projection(report: dict, artifact_ref: str) -> list[dict]:
    failures = []
    for case in report["cases"]:
        if case["status"] == "PASS": continue
        steps = [step for step in case.get("steps", []) if step.get("status") != "PASS"] or [None]
        for step in steps:
            failures.append({"case_id": case["case_id"], "step_id": step.get("id") if step else None,
                "status": case["status"], "failure_type": case.get("failure_type"),
                "safe_error_code": "QUERY_CASE_FAILED", "artifact_ref": artifact_ref})
    return failures
