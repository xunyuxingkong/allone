"""YAML 1.2 Core-style loading with duplicate-key rejection."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

from .errors import DuplicateKeyError, SourceSpan


class CoreYamlLoader(yaml.SafeLoader):
    pass


CoreYamlLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for _initial, _resolvers in CoreYamlLoader.yaml_implicit_resolvers.items():
    CoreYamlLoader.yaml_implicit_resolvers[_initial] = [
        pair
        for pair in _resolvers
        if pair[0] not in {"tag:yaml.org,2002:bool", "tag:yaml.org,2002:int", "tag:yaml.org,2002:float", "tag:yaml.org,2002:null", "tag:yaml.org,2002:timestamp"}
    ]
CoreYamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.IGNORECASE), list("tTfF")
)
CoreYamlLoader.add_implicit_resolver("tag:yaml.org,2002:null", re.compile(r"^(?:null|~)$", re.IGNORECASE), list("nN~"))
CoreYamlLoader.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^[-+]?(?:0|[1-9][0-9_]*|0o[0-7_]+|0x[0-9a-fA-F_]+)$"), list("-+0123456789"))
CoreYamlLoader.add_implicit_resolver("tag:yaml.org,2002:float", re.compile(r"^[-+]?(?:(?:[0-9][0-9_]*\.[0-9_]*)|(?:\.[0-9_]+)|(?:[0-9][0-9_]*[eE][-+]?[0-9]+)|(?:[0-9][0-9_]*\.[0-9_]*[eE][-+]?[0-9]+)|(?:\.inf)|(?:\.nan))$", re.IGNORECASE), list("-+.0123456789"))


def _construct_mapping(loader: CoreYamlLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise DuplicateKeyError(
                key,
                source=SourceSpan(
                    str(getattr(loader, "name", "<yaml>")),
                    key_node.start_mark.line + 1,
                    key_node.start_mark.column + 1,
                ),
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


CoreYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.load(stream, Loader=CoreYamlLoader)
