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
from .generator.plugins import FEATURE_PLUGINS
from .generator.scope import AcceptanceScope
from .query.compiler import QueryExecutable
from .generator.dedup import classify_duplicates
from .generator.lifecycle import promote_candidate, record_candidate_mutation_evidence, trial_candidate, validate_candidate_mutation
from .generator.review import record_review
from .generator.acceptance import verify_trial_artifact_index
from .generator.package import freeze_pre_promotion_manifest, preflight_promotion, verify_pre_promotion_package
from .generator.promotion_batch import execute_promotion_batch
from .generator.post_acceptance import freeze_post_promotion_package, verify_post_promotion_package, generate_final_acceptance
from .generator.release_checks import run_release_check, freeze_release_checks
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
            **{model.__name__: model for model in (ConstraintRule, CoverageStrategy, Dimension, TestModel, AcceptanceScope, QueryExecutable)},
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
    paths = FEATURE_PLUGINS.for_model(model.model_id).generate(model, args.strategy, cases, Path(args.output), limit=args.limit)
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
            results.append(FEATURE_PLUGINS.for_model(model.model_id).static_validate(path, model))
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
    action_status = {
        "KILLED": "PASS",
        "NOT_APPLICABLE": "SKIPPED",
        "WEAK": "FAIL",
        "BASELINE_NOT_PASS": "FAIL",
        "BASELINE_NONDETERMINISTIC": "BLOCKED",
        "INCONCLUSIVE": "BLOCKED",
        "MUTATED_NONDETERMINISTIC": "BLOCKED",
    }
    results = []
    for path in _candidate_paths(Path(args.path)):
        result = validate_candidate_mutation(path, model, config, profile)
        evidence = record_candidate_mutation_evidence(path, result, Path(args.artifacts), profile)
        results.append({**{key: value for key, value in result.items() if key != "execution"}, **evidence, "action_status": action_status[result["status"]]})
    passed = bool(results) and all(row["action_status"] in {"PASS", "SKIPPED"} for row in results)
    status = "PASS" if passed else "BLOCKED" if any(row["action_status"] == "BLOCKED" for row in results) else "FAIL"
    print(json.dumps({"candidates": results, "status": status}, ensure_ascii=False, sort_keys=True))
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
    raise ValueError(
        "SIGNED_BATCH_PROMOTION_REQUIRED: use acceptance promote-batch with a frozen manifest, "
        "operator-signed approval and allowed-signers trust store"
    )



def _acceptance_verify_trial_index(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = verify_trial_artifact_index(
        root,
        Path(args.index).resolve(),
        Path(args.runtime_profile).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


def _acceptance_freeze_package(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    scope = AcceptanceScope.model_validate_json(Path(args.scope_file).read_bytes()) if args.scope_file else None
    result = freeze_pre_promotion_manifest(root, Path(args.acceptance_dir), Path(args.runtime_profile), scope=scope)
    output = Path(args.manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"manifest": str(output), "manifest_id": result["manifest_id"], "count": len(result["members"])}, ensure_ascii=False, sort_keys=True))
    return 0


def _acceptance_verify_package(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    inputs = (root, Path(args.acceptance_dir), Path(args.runtime_profile), Path(args.manifest))
    approval_inputs = {
        "approval_path": Path(args.approval) if args.approval else None,
        "allowed_signers_path": Path(args.allowed_signers) if args.allowed_signers else None,
        "revoked_path": Path(args.revoked) if args.revoked else None,
    }
    result = preflight_promotion(*inputs, **approval_inputs) if args.preflight else verify_pre_promotion_package(*inputs, **approval_inputs)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["package_integrity"] == "PASS" and (not args.preflight or not result["blockers"]) else 1


def _acceptance_promote_batch(args: argparse.Namespace) -> int:
    result = execute_promotion_batch(
        Path(args.root), Path(args.acceptance_dir), Path(args.runtime_profile),
        Path(args.manifest), Path(args.approval), Path(args.allowed_signers),
        revoked_path=Path(args.revoked) if args.revoked else None,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _save_acceptance_result(result: dict, output: str | Path | None) -> None:
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


def _acceptance_post(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.acceptance_command == "freeze-post-package":
        result = freeze_post_promotion_package(root, candidate_manifest=Path(args.candidate_manifest), receipt=Path(args.receipt), regression=Path(args.regression), runtime_profile=Path(args.runtime_profile), approval=Path(args.approval), regression_build=Path(args.regression_build) if args.regression_build else None)
    else:
        keywords = {"allowed_signers_path": Path(args.allowed_signers), "revoked_path": Path(args.revoked) if args.revoked else None}
        if args.acceptance_command == "generate-final":
            result = generate_final_acceptance(root, Path(args.package), policy_path=Path(args.policy), release_checks_path=Path(args.release_checks) if args.release_checks else None, candidate_manifest_path=Path(args.candidate_manifest) if args.candidate_manifest else None, runtime_profile_path=Path(args.runtime_profile) if args.runtime_profile else None, acceptance_dir=Path(args.acceptance_dir) if args.acceptance_dir else None, **keywords)
        else:
            result = verify_post_promotion_package(root, Path(args.package), **keywords)
    _save_acceptance_result(result, args.output)
    return 0 if result.get("package_integrity", result.get("status", "PASS")) in {"PASS", "PASS_WITH_EXCEPTION"} else 1


def _acceptance_release_checks(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if args.acceptance_command == "run-release-check":
        result = run_release_check(root, args.kind)
    else:
        result = freeze_release_checks(root, {"framework": json.loads(Path(args.framework).read_text(encoding="utf-8"))["report"], "frontend": json.loads(Path(args.frontend).read_text(encoding="utf-8"))["report"]})
    _save_acceptance_result(result, args.output)
    return 0 if result.get("status", "PASS") == "PASS" else 1


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
    candidate_mutation_cmd.add_argument("--artifacts", default=root / "artifacts" / "mutations")
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
    candidate_promote.add_argument("--mutation-artifacts", default=root / "artifacts" / "mutations")
    candidate_promote.add_argument("--runtime-profile", required=True)
    candidate_promote.add_argument("--strategy", choices=("all_values", "pairwise"), default="pairwise")
    candidate_promote.add_argument("--snapshot", default=root / "artifacts" / "coverage" / "query.join-pairwise.json")
    candidate_promote.set_defaults(handler=_candidate_promote)
    candidate_dedup = candidate_commands.add_parser("dedup")
    candidate_dedup.add_argument("--path", default=root / "candidates" / "query" / "join")
    candidate_dedup.add_argument("--cases", default=root / "cases" / "query")
    candidate_dedup.add_argument("--model", default=root / "models" / "query" / "join.yaml")
    candidate_dedup.set_defaults(handler=_candidate_dedup)
    acceptance = commands.add_parser("acceptance")
    acceptance_commands = acceptance.add_subparsers(dest="acceptance_command", required=True)
    verify_trial_index = acceptance_commands.add_parser("verify-trial-index")
    verify_trial_index.add_argument("--root", default=root)
    verify_trial_index.add_argument("--index", default=root / "acceptance" / "query-generation-mvp" / "trial-run-index.json")
    verify_trial_index.add_argument("--runtime-profile", default=root / "artifacts" / "runtime-profile-v13.json")
    verify_trial_index.set_defaults(handler=_acceptance_verify_trial_index)
    for name, handler in (("freeze-package", _acceptance_freeze_package), ("verify-package", _acceptance_verify_package)):
        package_command = acceptance_commands.add_parser(name)
        package_command.add_argument("--root", default=root)
        package_command.add_argument("--acceptance-dir", default=root / "acceptance" / "query-generation-mvp")
        package_command.add_argument("--runtime-profile", default=root / "artifacts" / "runtime-profile-v13.json")
        package_command.add_argument("--manifest", default=root / "acceptance" / "query-generation-mvp" / "package-manifest.json")
        if name == "freeze-package":
            package_command.add_argument("--scope-file")
        if name == "verify-package":
            package_command.add_argument("--preflight", action="store_true")
            package_command.add_argument("--approval")
            package_command.add_argument("--allowed-signers")
            package_command.add_argument("--revoked", help="Revocation JSON list; a configured missing/invalid file fails closed")
        package_command.set_defaults(handler=handler)
    promote_batch = acceptance_commands.add_parser("promote-batch")
    promote_batch.add_argument("--root", default=root)
    promote_batch.add_argument("--acceptance-dir", default=root / "acceptance" / "query-generation-mvp")
    promote_batch.add_argument("--runtime-profile", default=root / "artifacts" / "runtime-profile-v13.json")
    promote_batch.add_argument("--manifest", default=root / "acceptance" / "query-generation-mvp" / "package-manifest.json")
    promote_batch.add_argument("--approval", required=True)
    promote_batch.add_argument("--allowed-signers", required=True)
    promote_batch.add_argument("--revoked")
    promote_batch.set_defaults(handler=_acceptance_promote_batch)
    for name in ("freeze-post-package", "verify-post-package", "generate-final"):
        command = acceptance_commands.add_parser(name)
        command.add_argument("--root", default=root)
        command.add_argument("--output")
        if name == "freeze-post-package":
            command.add_argument("--regression-build", help="Required by verifier when Runtime Profile records a DB build")
            for option in ("candidate-manifest", "receipt", "regression", "runtime-profile", "approval"):
                command.add_argument(f"--{option}", required=True)
        else:
            command.add_argument("--package", required=True)
            command.add_argument("--allowed-signers", required=True)
            command.add_argument("--revoked")
            if name == "generate-final":
                command.add_argument("--policy", default=root / "acceptance/query-generation-mvp/governance-policy.json")
                command.add_argument("--release-checks")
                command.add_argument("--candidate-manifest")
                command.add_argument("--runtime-profile")
                command.add_argument("--acceptance-dir")
        command.set_defaults(handler=_acceptance_post)
    for name in ("run-release-check", "freeze-release-checks"):
        command = acceptance_commands.add_parser(name)
        command.add_argument("--root", default=root)
        command.add_argument("--output", required=True)
        if name == "run-release-check":
            command.add_argument("kind", choices=("framework", "frontend"))
        else:
            command.add_argument("--framework", required=True)
            command.add_argument("--frontend", required=True)
        command.set_defaults(handler=_acceptance_release_checks)
    args = parser.parse_args()
    raise SystemExit(args.handler(args))
