"""Deterministic G0A core contract descriptor and content identity."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .canonical import xgmj1_sha256


DESCRIPTOR_VERSION = "3"
CONTRACT_VERSION = "1.1"
_SOURCE_DIRS = ("registry", "src/xgtest/core", "src/xgtest/query", "src/xgtest/design", "src/xgtest/generator", "framework_tests/contract", "framework_tests/design", "framework_tests/generator", "models", "generators")
_SOURCE_FILES = (
    "src/xgtest/cli.py",
    "src/xgtest/runtime/profile.py",
    "src/xgtest/runtime/comparator.py",
    "src/xgtest/adapter/xugu.py",
)
_GENERATED_DIRS = ("schemas",)
_GENERATED_FILES = ("src/xgtest/generated/registry_enums.py",)


def _content_hashes(root: Path, directories: tuple[str, ...], files: tuple[str, ...]) -> dict[str, str]:
    paths = [root / name for name in files if (root / name).is_file()]
    for directory in directories:
        paths.extend(path for path in (root / directory).rglob("*") if path.is_file() and path.suffix in {".py", ".yaml", ".json", ".ts", ".vue", ".css"})
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        for path in sorted(paths)
    }


def build_legacy_contract_descriptor(root: Path) -> dict[str, object]:
    """Retain the v1 algorithm for interpreting historical descriptors only."""
    root = root.resolve()
    sources = _content_hashes(root, _SOURCE_DIRS, _SOURCE_FILES)
    generated = _content_hashes(root, _GENERATED_DIRS, _GENERATED_FILES)
    identity = {
        "descriptor_version": "1",
        "contract_version": CONTRACT_VERSION,
        "generator": "xgtest.schema_export.v1",
        "sources": sources,
        "generated": generated,
    }
    return {**identity, "contract_set_id": xgmj1_sha256(identity)}


def build_contract_descriptor(root: Path) -> dict[str, object]:
    """Execution identity is independent of governance, CLI/Web and tests.

    Worker models are physically separate; coordinator assets, evidence, admission
    and publication locks are governance dependencies, not execution inputs.
    """
    root = root.resolve()
    dependencies = {
        "runtime": (("src/xgtest/adapter",), ("src/xgtest/runtime/profile.py",)),
        "comparison": ((), ("src/xgtest/runtime/comparator.py", "src/xgtest/core/canonical.py", "src/xgtest/core/logical_types.py", "src/xgtest/core/row_codec.py")),
        "execution_schema": ((), ("src/xgtest/core/model_base.py", "src/xgtest/core/execution_models.py", "src/xgtest/core/errors.py", "src/xgtest/query/compiler.py", "src/xgtest/query/runner.py", "src/xgtest/query/result.py", "src/xgtest/query/timeout.py", "src/xgtest/generated/registry_enums.py", "schemas/QueryExecutable.schema.json", "schemas/QueryRunReport.schema.json", "schemas/RuntimeProfile.schema.json")),
        "design": (("src/xgtest/design", "models"), ()),
        "generator": (("generators",), ("src/xgtest/generator/candidate.py", "src/xgtest/generator/template.py", "src/xgtest/generator/plugins.py")),
        "governance": (("src/xgtest/generator", "registry"), ("src/xgtest/core/evidence_models.py", "src/xgtest/core/governance_models.py", "src/xgtest/core/control_models.py", "src/xgtest/core/admission.py", "src/xgtest/core/manifest.py", "src/xgtest/core/identity.py", "src/xgtest/core/metadata.py", "src/xgtest/core/yaml_loader.py", "src/xgtest/core/asset_lock.py", "src/xgtest/query/loader.py")),
        "control_plane": (("src/xgtest/web", "webui/src"), ("src/xgtest/cli.py", "webui/vite.config.ts")),
        "suite": (("framework_tests",), ()),
    }
    layers = {}
    for name, (directories, files) in dependencies.items():
        sources = _content_hashes(root, directories, files)
        if name == "governance":
            sources = {path: digest for path, digest in sources.items() if path not in {"src/xgtest/generator/candidate.py", "src/xgtest/generator/template.py", "src/xgtest/generator/plugins.py"}}
        projection = {"schema_version": "1", "layer": name, "sources": sources}
        layers[name] = {**projection, "id": xgmj1_sha256(projection)}
    execution = {name: layers[name]["id"] for name in ("runtime", "comparison", "execution_schema")}
    sources = _content_hashes(root, ("registry", "src/xgtest/core", "src/xgtest/query", "src/xgtest/design", "src/xgtest/generator", "models", "generators"), _SOURCE_FILES[1:])
    generated = _content_hashes(root, _GENERATED_DIRS, _GENERATED_FILES)
    return {"descriptor_version": DESCRIPTOR_VERSION, "contract_version": "3.0",
            "identity_kind": "execution", "execution_projection": execution,
            "contract_set_id": xgmj1_sha256(execution), "layers": layers,
            "sources": sources, "generated": generated}


def validate_contract_descriptor(descriptor: dict[str, object]) -> None:
    """Validate stored v1/v2 identities without silently reinterpreting old IDs."""
    if descriptor.get("descriptor_version") == "1":
        identity = {key: value for key, value in descriptor.items() if key != "contract_set_id"}
        if descriptor.get("contract_set_id") != xgmj1_sha256(identity):
            raise ValueError("LEGACY_CONTRACT_DESCRIPTOR_ID_INVALID")
    elif descriptor.get("descriptor_version") in {"2", "3"}:
        layers = descriptor["layers"]
        for name, layer in layers.items():
            if layer.get("layer") != name or layer["id"] != xgmj1_sha256({key: value for key, value in layer.items() if key != "id"}):
                raise ValueError("CONTRACT_LAYER_ID_INVALID")
        execution = {name: layers[name]["id"] for name in ("runtime", "comparison", "execution_schema")}
        if descriptor.get("execution_projection") != execution or descriptor.get("contract_set_id") != xgmj1_sha256(execution):
            raise ValueError("EXECUTION_CONTRACT_ID_INVALID")
    else:
        raise ValueError("CONTRACT_DESCRIPTOR_VERSION_UNSUPPORTED")
