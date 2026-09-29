"""Small CLI for Phase 0A contract verification."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from .core.models import MODEL_EXPORTS
from .core.registry import generate_enums_module, load_registry
from .adapter.xugu import XuguConnectionConfig
from .runtime.runner import run_cases
from .runtime.profile import build_profile_file, load_profile
from .core.contract_set import build_contract_descriptor
from .query.loader import validate_query_directory
from .query.runner import run_query_cases
from .design.model import load_test_model
from .design.coverage import FileCoverageSource, coverage_gap
from .generator.candidate import generate_candidates, static_validate_candidate
from .generator.dedup import classify_duplicates
from .generator.lifecycle import promote_candidate, trial_candidate, validate_candidate_mutation
from .generator.review import record_review
from .design.model import ConstraintRule, CoverageStrategy, Dimension, TestModel
from .query.loader import load_query_directory


CONTRACT_VERSION = "1.1"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _registry_validate(args: argparse.Namespace) -> int:
    registry = load_registry(Path(args.registry))
    payload = {
        name: [
            {"key": entry.key, **entry.metadata}
            for entry in entries
        ]
        for name, entries in sorted(registry.entries.items())
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _registry_generate(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_enums_module(load_registry(Path(args.registry))), encoding="utf-8")
    return 0


def _schema_export(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temporary:
        generated = Path(temporary) / "schemas"
        generated.mkdir()
        exported_models = {
            **MODEL_EXPORTS,
            **{model.__name__: model for model in (ConstraintRule, CoverageStrategy, Dimension, TestModel)},
        }
        for name, model in exported_models.items():
            schema = model.model_json_schema()
            schema["$id"] = f"xgtest://schema/{CONTRACT_VERSION}/{name}"
            schema["x-xg-contract-version"] = CONTRACT_VERSION
            (generated / f"{name}.schema.json").write_text(
                json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
        if output.exists():
            shutil.rmtree(output)
        shutil.move(str(generated), str(output))
    return 0


def _run_mvp(args: argparse.Namespace) -> int:
    profile = load_profile(Path(args.runtime_profile)) if args.runtime_profile else None
    report = run_cases(XuguConnectionConfig.from_environment(), Path(args.cases), Path(args.output), args.runtime_profile_id, profile)
    print(json.dumps({"output": args.output, "status": report["status"], "cases": len(report["cases"])}, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def _profile_build(args: argparse.Namespace) -> int:
    profile = build_profile_file(Path(args.evidence), Path(args.output))
    print(json.dumps({"output": args.output, "sql_runtime_profile_id": profile["sql_runtime_profile_id"]}, ensure_ascii=False, sort_keys=True))
    return 0


def _contract_verify(args: argparse.Namespace) -> int:
    descriptor = build_contract_descriptor(Path(args.root))
    expected_path = Path(args.candidate)
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    if descriptor != expected:
        print("CONTRACT_DESCRIPTOR_STALE")
        return 1
    print("CONTRACT_DESCRIPTOR_OK")
    return 0


def _contract_build(args: argparse.Namespace) -> int:
    descriptor = build_contract_descriptor(Path(args.root))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "contract_set_id": descriptor["contract_set_id"]}, sort_keys=True))
    return 0


def _query_validate(args: argparse.Namespace) -> int:
    report = validate_query_directory(Path(args.cases))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def _query_run(args: argparse.Namespace) -> int:
    profile = load_profile(Path(args.runtime_profile)) if args.runtime_profile else None
    report = run_query_cases(
        XuguConnectionConfig.from_environment(),
        Path(args.cases),
        Path(args.output),
        runtime_profile=profile,
        mode=args.mode,
    )
    print(json.dumps({"output": args.output, "status": report["status"], "cases": len(report["cases"])}, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


def _web_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError as error:
        raise RuntimeError("install xgtest[web] to run the Query MVP web API") from error
    uvicorn.run("xgtest.web.app:app", host=args.host, port=args.port, reload=False)
    return 0


def _model_validate(args: argparse.Namespace) -> int:
    model = load_test_model(Path(args.model))
    print(json.dumps({"status": "PASS", "model_id": model.model_id, "model_version": model.model_version, "dimensions": len(model.dimensions)}, sort_keys=True))
    return 0


def _generation_model(args: argparse.Namespace):
    model = load_test_model(Path(args.model))
    if model.model_id != args.model_id:
        raise ValueError(f"MODEL_ID_MISMATCH: expected {args.model_id}, found {model.model_id}")
    return model


def _coverage_report(args: argparse.Namespace) -> int:
    model = _generation_model(args)
    cases = load_query_directory(Path(args.cases))
    source = FileCoverageSource(cases)
    strategies = [args.strategy] if args.strategy else ["all_values", "pairwise"]
    output = []
    for strategy in strategies:
        gap = coverage_gap(model, source, strategy)
        output.append({
            "model_id": model.model_id,
            "model_version": model.model_version,
            "strategy": strategy,
            "active_case_count": sum(case.metadata.status.value == "active" for case in cases),
            "required": gap["required"],
            "covered": gap["covered"],
            "missing": gap["missing"],
            "missing_requirements": [
                {"requirement_id": req.requirement_id, "selections": dict(req.selections)}
                for req in gap["missing_requirements"]
            ] if args.show_missing else None,
        })
    print(json.dumps(output if len(output) > 1 else output[0], ensure_ascii=False, sort_keys=True))
    return 0


def _generate(args: argparse.Namespace) -> int:
    model = _generation_model(args)
    cases = load_query_directory(Path(args.cases))
    paths = generate_candidates(model, args.strategy, cases, Path(args.output), limit=args.limit)
    from .query.loader import load_query_case
    candidate_cases = tuple(load_query_case(path) for path in paths)
    duplicates = [item for item in classify_duplicates((*cases, *candidate_cases), model) if item["classification"] != "UNIQUE"]
    print(json.dumps({"status": "PASS", "generated": len(paths), "candidates": [str(path) for path in paths], "duplicate_review": duplicates}, ensure_ascii=False, sort_keys=True))
    return 0


def _candidate_paths(location: Path) -> list[Path]:
    if location.is_file():
        return [location]
    return sorted((*location.rglob("*.yaml"), *location.rglob("*.yml")))


def _candidate_validate(args: argparse.Namespace) -> int:
    model = load_test_model(Path(args.model))
    results = []
    for path in _candidate_paths(Path(args.path)):
        try:
            results.append(static_validate_candidate(path, model))
        except ValueError as error:
            results.append({"path": str(path), "status": "FAIL", "error": str(error)})
    print(json.dumps({"candidates": results, "status": "PASS" if results and all(row.get("status") == "draft" for row in results) else "FAIL"}, ensure_ascii=False, sort_keys=True))
    return 0 if results and all(row.get("status") == "draft" for row in results) else 1


def _candidate_trial(args: argparse.Namespace) -> int:
    model = load_test_model(Path(args.model))
    profile = load_profile(Path(args.runtime_profile)) if args.runtime_profile else None
    result = trial_candidate(
        Path(args.path), model, XuguConnectionConfig.from_environment(), Path(args.artifacts), runtime_profile=profile,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _candidate_mutation_validate(args: argparse.Namespace) -> int:
    model = load_test_model(Path(args.model))
    profile = load_profile(Path(args.runtime_profile))
    config = XuguConnectionConfig.from_environment()
    results = [
        validate_candidate_mutation(path, model, config, profile)
        for path in _candidate_paths(Path(args.path))
    ]
    applicable = [row for row in results if row["status"] != "NOT_APPLICABLE"]
    passed = bool(applicable) and all(row["status"] == "KILLED" for row in applicable)
    print(json.dumps({"candidates": results, "status": "PASS" if passed else "FAIL"}, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


def _candidate_list(args: argparse.Namespace) -> int:
    from .query.loader import load_query_case

    rows = []
    for path in _candidate_paths(Path(args.path)):
        try:
            case = load_query_case(path)
        except ValueError as error:
            rows.append({"path": str(path), "status": "INVALID", "error": str(error)})
            continue
        if args.status is None or case.metadata.status.value == args.status:
            rows.append({"case_id": case.metadata.id, "status": case.metadata.status.value, "path": str(path)})
    print(json.dumps(rows, ensure_ascii=False, sort_keys=True))
    return 0


def _candidate_dedup(args: argparse.Namespace) -> int:
    from .query.loader import load_query_case

    model = load_test_model(Path(args.model))
    cases = list(load_query_directory(Path(args.cases)))
    errors = []
    for path in _candidate_paths(Path(args.path)):
        try:
            cases.append(load_query_case(path))
        except ValueError as error:
            errors.append({"path": str(path), "error": str(error)})
    result = classify_duplicates(cases, model)
    print(json.dumps({"duplicates": result, "invalid_candidates": errors}, ensure_ascii=False, sort_keys=True))
    return 1 if errors else 0


def _candidate_review(args: argparse.Namespace) -> int:
    matches = list(Path(args.path).rglob(f"{args.case_id}.yaml"))
    if len(matches) != 1:
        raise ValueError(f"CANDIDATE_ID_MATCH_COUNT: {args.case_id}: {len(matches)}")
    result = record_review(
        matches[0], model=load_test_model(Path(args.model)), reviewer=args.reviewer,
        review_reference=args.reference, coverage_reference=args.coverage_reference,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _candidate_promote(args: argparse.Namespace) -> int:
    model = load_test_model(Path(args.model))
    profile = load_profile(Path(args.runtime_profile))
    current_contract_set_id = build_contract_descriptor(_project_root())["contract_set_id"]
    if profile["identity"].get("contract_set_id") != current_contract_set_id:
        raise ValueError("RUNTIME_PROFILE_MISMATCH: contract set differs")
    matches = list(Path(args.path).rglob(f"{args.case_id}.yaml"))
    if len(matches) != 1:
        raise ValueError(f"CANDIDATE_ID_MATCH_COUNT: {args.case_id}: {len(matches)}")
    destination = promote_candidate(
        matches[0], model, Path(args.cases), Path(args.artifacts),
        expected_runtime_profile_id=profile["sql_runtime_profile_id"],
    )
    active = load_query_directory(Path(args.cases))
    all_claims = [claim for case in active if case.metadata.status.value == "active" for claim in case.coverage]
    strategy_snapshots = {}
    for strategy in ("all_values", "pairwise"):
        strategy_gap = coverage_gap(model, all_claims, strategy)
        strategy_snapshots[strategy] = {
            "required": strategy_gap["required"],
            "covered": strategy_gap["covered"],
            "missing": strategy_gap["missing"],
        }
    snapshot = {
        "model_id": model.model_id,
        "model_version": model.model_version,
        "strategies": strategy_snapshots,
        "gap": strategy_snapshots[args.strategy]["missing"],
    }
    snapshot_path = Path(args.snapshot)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "active", "case": str(destination), "coverage_snapshot": str(snapshot_path), "coverage": snapshot}, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> None:
    root = _project_root()
    parser = argparse.ArgumentParser(prog="xgtest")
    commands = parser.add_subparsers(dest="command", required=True)
    registry = commands.add_parser("registry")
    registry_commands = registry.add_subparsers(dest="registry_command", required=True)
    validate = registry_commands.add_parser("validate")
    validate.add_argument("--registry", default=root / "registry")
    validate.set_defaults(handler=_registry_validate)
    generate = registry_commands.add_parser("generate-enums")
    generate.add_argument("--registry", default=root / "registry")
    generate.add_argument("--output", default=root / "src" / "xgtest" / "generated" / "registry_enums.py")
    generate.set_defaults(handler=_registry_generate)
    schema = commands.add_parser("schema")
    schema_commands = schema.add_subparsers(dest="schema_command", required=True)
    export = schema_commands.add_parser("export")
    export.add_argument("--output", default=root / "schemas")
    export.set_defaults(handler=_schema_export)
    run = commands.add_parser("run")
    run.add_argument("--cases", default=root / "cases" / "mvp")
    run.add_argument("--output", default=Path("artifacts") / "runs" / "latest.json")
    run.add_argument("--runtime-profile-id")
    run.add_argument("--runtime-profile")
    run.set_defaults(handler=_run_mvp)
    profile = commands.add_parser("profile")
    profile_commands = profile.add_subparsers(dest="profile_command", required=True)
    build = profile_commands.add_parser("build")
    build.add_argument("--evidence", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(handler=_profile_build)
    contract = commands.add_parser("contract")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    verify = contract_commands.add_parser("verify")
    verify.add_argument("--root", default=root)
    verify.add_argument("--candidate", default=root / "docs" / "g0a" / "contract-descriptor-candidate.json")
    verify.set_defaults(handler=_contract_verify)
    contract_build = contract_commands.add_parser("build")
    contract_build.add_argument("--root", default=root)
    contract_build.add_argument("--output", default=root / "docs" / "g0a" / "contract-descriptor-candidate.json")
    contract_build.set_defaults(handler=_contract_build)
    query = commands.add_parser("query")
    query_commands = query.add_subparsers(dest="query_command", required=True)
    query_validate = query_commands.add_parser("validate")
    query_validate.add_argument("--cases", default=root / "cases" / "query")
    query_validate.set_defaults(handler=_query_validate)
    query_run = query_commands.add_parser("run")
    query_run.add_argument("--cases", default=root / "cases" / "query")
    query_run.add_argument("--output", default=Path("artifacts") / "runs" / "query-latest.json")
    query_run.add_argument("--runtime-profile")
    query_run.add_argument("--mode", choices=("diagnostic", "regression"), default="regression")
    query_run.set_defaults(handler=_query_run)
    web = commands.add_parser("web")
    web_commands = web.add_subparsers(dest="web_command", required=True)
    serve = web_commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(handler=_web_serve)

    model = commands.add_parser("model")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_validate = model_commands.add_parser("validate")
    model_validate.add_argument("model", nargs="?", default=root / "models" / "query" / "join.yaml")
    model_validate.set_defaults(handler=_model_validate)

    coverage = commands.add_parser("coverage")
    coverage_commands = coverage.add_subparsers(dest="coverage_command", required=True)
    for name, show_missing in (("show", False), ("gap", True)):
        coverage_cmd = coverage_commands.add_parser(name)
        coverage_cmd.add_argument("model_id")
        coverage_cmd.add_argument("--model", default=root / "models" / "query" / "join.yaml")
        coverage_cmd.add_argument("--cases", default=root / "cases" / "query")
        coverage_cmd.add_argument("--strategy", choices=("all_values", "pairwise"))
        coverage_cmd.add_argument("--show-missing", action="store_true", default=show_missing)
        coverage_cmd.set_defaults(handler=_coverage_report)

    generate_cmd = commands.add_parser("generate")
    generate_cmd.add_argument("model_id")
    generate_cmd.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    generate_cmd.add_argument("--strategy", choices=("all_values", "pairwise"), required=True)
    generate_cmd.add_argument("--cases", default=root / "cases" / "query")
    generate_cmd.add_argument("--output", default=root / "candidates" / "query" / "join")
    generate_cmd.add_argument("--limit", type=int)
    generate_cmd.set_defaults(handler=_generate)

    candidate = commands.add_parser("candidate")
    candidate_commands = candidate.add_subparsers(dest="candidate_command", required=True)
    candidate_validate = candidate_commands.add_parser("validate")
    candidate_validate.add_argument("path")
    candidate_validate.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    candidate_validate.set_defaults(handler=_candidate_validate)
    candidate_trial_cmd = candidate_commands.add_parser("trial")
    candidate_trial_cmd.add_argument("path")
    candidate_trial_cmd.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    candidate_trial_cmd.add_argument("--artifacts", default=root / "artifacts" / "trial-runs")
    candidate_trial_cmd.add_argument("--runtime-profile", required=True)
    candidate_trial_cmd.set_defaults(handler=_candidate_trial)
    candidate_mutation_cmd = candidate_commands.add_parser("mutation-validate")
    candidate_mutation_cmd.add_argument("path")
    candidate_mutation_cmd.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    candidate_mutation_cmd.add_argument("--runtime-profile", required=True)
    candidate_mutation_cmd.set_defaults(handler=_candidate_mutation_validate)
    candidate_list = candidate_commands.add_parser("list")
    candidate_list.add_argument("--path", default=root / "candidates" / "query" / "join")
    candidate_list.add_argument("--status", choices=("generated", "draft", "review", "active"))
    candidate_list.set_defaults(handler=_candidate_list)
    candidate_review_cmd = candidate_commands.add_parser("review")
    candidate_review_cmd.add_argument("case_id")
    candidate_review_cmd.add_argument("--path", default=root / "candidates" / "query" / "join")
    candidate_review_cmd.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    candidate_review_cmd.add_argument("--reviewer", required=True)
    candidate_review_cmd.add_argument("--reference", required=True)
    candidate_review_cmd.add_argument("--coverage-reference", required=True)
    candidate_review_cmd.set_defaults(handler=_candidate_review)
    candidate_promote = candidate_commands.add_parser("promote")
    candidate_promote.add_argument("case_id")
    candidate_promote.add_argument("--path", default=root / "candidates" / "query" / "join")
    candidate_promote.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    candidate_promote.add_argument("--cases", default=root / "cases" / "query")
    candidate_promote.add_argument("--artifacts", default=root / "artifacts" / "trial-runs")
    candidate_promote.add_argument("--runtime-profile", required=True)
    candidate_promote.add_argument("--strategy", choices=("all_values", "pairwise"), default="pairwise")
    candidate_promote.add_argument("--snapshot", default=root / "artifacts" / "coverage" / "query.join-pairwise.json")
    candidate_promote.set_defaults(handler=_candidate_promote)
    candidate_dedup = candidate_commands.add_parser("dedup")
    candidate_dedup.add_argument("--path", default=root / "candidates" / "query" / "join")
    candidate_dedup.add_argument("--cases", default=root / "cases" / "query")
    candidate_dedup.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    candidate_dedup.set_defaults(handler=_candidate_dedup)
    args = parser.parse_args()
    raise SystemExit(args.handler(args))
