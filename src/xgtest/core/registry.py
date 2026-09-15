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
class Registry:
    entries: dict[str, tuple[str, ...]]

    def keys(self, name: str) -> tuple[str, ...]:
        return self.entries[name]

    def require(self, name: str, key: str) -> None:
        if key not in self.keys(name):
            raise ContractError("UNKNOWN_REGISTRY_KEY", f"registry.{name}", key)


def _item_keys(raw: Any, path: Path) -> tuple[str, ...]:
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
        raise ContractError("REGISTRY_SHAPE", str(path), "items must be a list")
    keys: list[str] = []
    for index, item in enumerate(raw["items"]):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise ContractError("REGISTRY_ENTRY", f"{path}:items[{index}]", "key must be a string")
        keys.append(item["key"])
    if len(keys) != len(set(keys)):
        raise ContractError("REGISTRY_DUPLICATE_KEY", str(path), "keys must be unique")
    return tuple(keys)


def load_registry(root: Path) -> Registry:
    entries: dict[str, tuple[str, ...]] = {}
    for name in ITEM_REGISTRIES:
        entries[name] = _item_keys(load_yaml(root / f"{name}.yaml"), root / f"{name}.yaml")
    raw_statuses = load_yaml(root / "statuses.yaml")
    if not isinstance(raw_statuses, dict):
        raise ContractError("REGISTRY_SHAPE", "statuses.yaml", "must be a mapping")
    for namespace, values in raw_statuses.items():
        if not isinstance(namespace, str) or not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ContractError("REGISTRY_ENTRY", "statuses.yaml", "namespace values must be string lists")
        if len(values) != len(set(values)):
            raise ContractError("REGISTRY_DUPLICATE_KEY", f"statuses.{namespace}", "values must be unique")
        entries[f"statuses.{namespace}"] = tuple(values)
    return Registry(entries=entries)


def generate_enums_module(registry: Registry) -> str:
    lines = ["# Generated from registry/*.yaml; do not edit.", "from enum import StrEnum", ""]
    for name in sorted(registry.entries):
        class_name = "".join(part.title() for part in name.replace(".", "_").split("_"))
        lines.append(f"class {class_name}(StrEnum):")
        for key in registry.keys(name):
            member = key.upper().replace(".", "_").replace("-", "_")
            lines.append(f'    {member} = "{key}"')
        lines.append("")
    return "\n".join(lines)

\n