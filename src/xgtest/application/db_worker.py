"""Trusted local/WSL bridge for existing Xugu operations; no model-written SQL."""
import json
import sys
import socket
from pathlib import Path
from xgtest.adapter.xugu import XuguConnectionConfig
from xgtest.core.contract_set import build_contract_descriptor
from xgtest.generator.lifecycle import validate_candidate_mutations, record_candidate_mutation_evidence, trial_candidate
from xgtest.generator.scope import resolve_scope
from xgtest.query.runner import run_query_cases
from xgtest.runtime.profile import load_profile, validate_profile, observe_database_build
from xgtest.application.worker_results import safe_worker_error, failure_projection


def execute(root: Path, request: dict) -> dict:
    import xgcondb
    scope = resolve_scope()
    config = XuguConnectionConfig.from_environment()
    profile_path = (root / request["profile"]).resolve()
    directory = (root / request["directory"]).resolve()
    if not directory.is_relative_to((root / "artifacts/jobs").resolve()) or not profile_path.is_relative_to(root):
        raise ValueError("DB_REQUEST_PATH_INVALID")
    directory.mkdir(parents=True, exist_ok=True)
    profile = load_profile(profile_path)
    validate_profile(profile, host=config.host, database=config.database, driver_version=tuple(xgcondb.version_info),
                     contract_set_id=build_contract_descriptor(root)["contract_set_id"])
    operation = request["operation"]
    try:
        with socket.create_connection((config.host, int(config.port)), timeout=5):
            pass
    except OSError:
        return {"status": "BLOCKED", "error": "DATABASE_NETWORK_UNREACHABLE"}
    if operation == "preflight":
        observation = observe_database_build(config, profile)
        (directory / "database-build.json").write_text(json.dumps(observation, indent=2), encoding="utf-8")
        return {"status": "PASS", "observation": observation}
    if operation == "regression":
        before = observe_database_build(config, profile)
        report = run_query_cases(config, scope.path(root, "active_suite_root"), directory / "regression.json", runtime_profile=profile)
        after = observe_database_build(config, profile)
        (directory / "regression-build.json").write_text(json.dumps({"before": before, "after": after}, indent=2), encoding="utf-8")
        return {"status": report["status"], "case_count": len(report["cases"]),
                "failures": failure_projection(report, (directory / "regression.json").relative_to(root).as_posix())}
    import re
    case_id = request.get("case_id", "")
    if not re.fullmatch(r"QUERY\.JOIN\.[A-Z0-9]+", case_id):
        raise ValueError("DB_REQUEST_CASE_ID_INVALID")
    path = scope.path(root, "candidate_root") / f"{case_id}.yaml"
    model = scope.load_model(root)
    if operation == "mutation":
        checks = validate_candidate_mutations(path, model, config, profile)
        if any(check["status"] not in {"KILLED", "NOT_APPLICABLE"} for check in checks):
            return {"status": "FAIL", "checks": [{key: value for key, value in check.items() if key != "execution"} for check in checks]}
        evidence = record_candidate_mutation_evidence(path, checks, root / "artifacts/mutations", profile)
        return {"status": "PASS", "checks": [{key: value for key, value in check.items() if key != "execution"} for check in checks], "evidence": evidence}
    if operation == "trial":
        return {**trial_candidate(path, model, config, root / "artifacts/trial-runs", runtime_profile=profile), "status": "PASS"}
    raise ValueError("DB_OPERATION_UNSUPPORTED")


def main():
    root = Path(__file__).resolve().parents[3]
    path = (root / sys.argv[1]).resolve()
    if not path.is_relative_to((root / "artifacts/jobs").resolve()):
        raise ValueError("DB_REQUEST_PATH_INVALID")
    try:
        result = execute(root, json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, RuntimeError, ImportError, OSError) as error:
        result = safe_worker_error(error)
    except Exception as error:
        # DB-API driver exceptions need not inherit the standard runtime exceptions.
        result = safe_worker_error(error)
    path.with_suffix(".result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
