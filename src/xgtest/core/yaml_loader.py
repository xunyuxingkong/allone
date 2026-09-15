"""YAML 1.2 Core-style loading with duplicate-key rejection."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

from .errors import DuplicateKeyError


class CoreYamlLoader(yaml.SafeLoader):
    pass


CoreYamlLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for _initial, _resolvers in CoreYamlLoader.yaml_implicit_resolvers.items():
    CoreYamlLoader.yaml_implicit_resolvers[_initial] = [
        pair
        for pair in _resolvers
        if pair[0] not in {"tag:yaml.org,2002:bool", "tag:yaml.org,2002:timestamp"}
    ]
CoreYamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf")
)


def _construct_mapping(loader: CoreYamlLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKeyError(key)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


CoreYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.load(stream, Loader=CoreYamlLoader)

\n