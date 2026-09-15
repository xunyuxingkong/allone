"""Registry loading and deterministic Python enum generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ContractError
from .yaml_loader import load_yaml


ITEM_REGISTRIES = (
    "features",
    "capabilities",
    "levels",
    "failure_types",
    "isolation_scopes",
    "resource_access_modes",
)
NAMESPACED_REGISTRIES = ("statuses",)


@dataclass(frozen=True)
class RegistryEntry:
    key: str
    metadata: dict[str, Any]


_ENUM_CLASS_NAMES = {
    "features": "FeatureKey",
    "capabilities": "CapabilityKey",
    "levels": "Level",
    "failure_types": "FailureType",
    "isolation_scopes": "IsolationScope",
    "resource_access_modes": "ResourceAccessMode",
    "statuses.case_asset": "CaseAssetStatus",
    "statuses.case_execution": "CaseExecutionStatus",
    "statuses.attempt": "AttemptStatus",
    "statuses.step": "StepStatus",
}


@dataclass(frozen=True)
class Registry:
    entries: dict[str, tuple[RegistryEntry, ...]]

    def keys(self, name: str) -> tuple[str, ...]:
        return tuple(entry.key for entry in self.entries[name])

    def get(self, name: str, key: str) -> RegistryEntry:
        for entry in self.entries[name]:
            if entry.key == key:
                return entry
        raise ContractError("UNKNOWN_REGISTRY_KEY", f"registry.{name}", key)

    def require(self, name: str, key: str) -> None:
        if key not in self.keys(name):
            raise ContractError("UNKNOWN_REGISTRY_KEY", f"registry.{name}", key)


def _item_entries(raw: Any, path: Path) -> tuple[RegistryEntry, ...]:
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise ContractError("REGISTRY_SHAPE", str(path), "items must be a list")
    entries: list[RegistryEntry] = []
    for index, item in enumerate(raw["items"]):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise ContractError("REGISTRY_ENTRY", f"{path}:items[{index}]", "key must be a string")
        entries.append(RegistryEntry(key=item["key"], metadata={key: value for key, value in item.items() if key != "key"}))
    keys = [entry.key for entry in entries]
    if len(keys) != len(set(keys)):
        raise ContractError("REGISTRY_DUPLICATE_KEY", str(path), "keys must be unique")
    return tuple(entries)


def load_registry(root: Path) -> Registry:
    entries: dict[str, tuple[RegistryEntry, ...]] = {}
    for name in ITEM_REGISTRIES:
        entries[name] = _item_entries(load_yaml(root / f"{name}.yaml"), root / f"{name}.yaml")
    raw_statuses = load_yaml(root / "statuses.yaml")
    if not isinstance(raw_statuses, dict):
        raise ContractError("REGISTRY_SHAPE", "statuses.yaml", "must be a mapping")
    for namespace, values in raw_statuses.items():
        if not isinstance(namespace, str) or not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ContractError("REGISTRY_ENTRY", "statuses.yaml", "namespace values must be string lists")
        if len(values) != len(set(values)):
            raise ContractError("REGISTRY_DUPLICATE_KEY", f"statuses.{namespace}", "values must be unique")
        entries[f"statuses.{namespace}"] = tuple(RegistryEntry(key=value, metadata={}) for value in values)
    return Registry(entries=entries)


def generate_enums_module(registry: Registry) -> str:
    lines = ["# Generated from registry/*.yaml; do not edit.", "from enum import StrEnum", ""]
    for name in sorted(registry.entries):
        class_name = _ENUM_CLASS_NAMES.get(name, "".join(part.title() for part in name.replace(".", "_").split("_")))
        lines.append(f"class {class_name}(StrEnum):")
        members: dict[str, str] = {}
        for key in registry.keys(name):
            member = key.upper().replace(".", "_").replace("-", "_")
            if member in members:
                raise ContractError("REGISTRY_ENUM_NAME_COLLISION", f"registry.{name}", f"{members[member]!r} and {key!r} both map to {member}")
            members[member] = key
            lines.append(f'    {member} = "{key}"')
        lines.append("")
    return "\n".join(lines)
