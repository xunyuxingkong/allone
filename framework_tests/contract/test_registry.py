from pathlib import Path

import pytest

from xgtest.core.errors import DuplicateKeyError
from xgtest.core.errors import ContractError
from xgtest.core.registry import Registry, RegistryEntry, generate_enums_module, load_registry
from xgtest.core.yaml_loader import load_yaml
from xgtest.cli import _project_root


ROOT = Path(__file__).resolve().parents[2]


def test_registry_loads_and_generates_deterministically() -> None:
    registry = load_registry(ROOT / "registry")
    assert registry.keys("features") == ("join", "union", "ddl_table", "string_function")
    assert registry.get("features", "join").metadata == {"phase": "sql_mvp"}
    first = generate_enums_module(registry)
    assert first == generate_enums_module(registry)
    assert 'JOIN = "join"' in first


def test_cli_project_root_is_repository_root() -> None:
    assert _project_root() == ROOT


def test_yaml_rejects_duplicate_keys(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text("a: 1\na: 2\n", encoding="utf-8")
    with pytest.raises(DuplicateKeyError, match="DUPLICATE_KEY"):
        load_yaml(duplicate)


def test_yaml_uses_core_boolean_handling(tmp_path: Path) -> None:
    source = tmp_path / "core.yaml"
    source.write_text("enabled: true\nlegacy: on\n", encoding="utf-8")
    assert load_yaml(source) == {"enabled": True, "legacy": "on"}


def test_yaml_core_scalar_edges(tmp_path: Path) -> None:
    source = tmp_path / "core-edges.yaml"
    source.write_text("legacy: 0123\noctal: 0o123\nhex: 0x10\ninf: .inf\ntimestamp: 2026-09-15\n", encoding="utf-8")
    loaded = load_yaml(source)
    assert loaded["legacy"] == "0123"
    assert loaded["octal"] == 83
    assert loaded["hex"] == 16
    assert loaded["inf"] == float("inf")
    assert loaded["timestamp"] == "2026-09-15"


def test_enum_member_name_collision_is_rejected() -> None:
    registry = Registry(entries={"features": (RegistryEntry("a-b", {}), RegistryEntry("a_b", {}))})
    with pytest.raises(ContractError, match="REGISTRY_ENUM_NAME_COLLISION"):
        generate_enums_module(registry)
