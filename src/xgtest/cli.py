"""Small CLI for Phase 0A contract verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core.models import MODEL_EXPORTS
from .core.registry import generate_enums_module, load_registry


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _registry_validate(args: argparse.Namespace) -> int:
    registry = load_registry(Path(args.registry))
    print(json.dumps({name: list(values) for name, values in sorted(registry.entries.items())}, ensure_ascii=False, sort_keys=True))
    return 0


def _registry_generate(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generate_enums_module(load_registry(Path(args.registry))), encoding="utf-8")
    return 0


def _schema_export(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for name, model in MODEL_EXPORTS.items():
        (output / f"{name}.schema.json").write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
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
    args = parser.parse_args()
    raise SystemExit(args.handler(args))
