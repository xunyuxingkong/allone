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
        for name, model in MODEL_EXPORTS.items():
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
    args = parser.parse_args()
    raise SystemExit(args.handler(args))
