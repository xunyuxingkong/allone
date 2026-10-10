"""Feature-neutral case hashing plus the default feature's template re-exports.

`semantic_hash` is feature-agnostic: it hashes only each step's SQL, expected
result and comparison. Renderers are feature policy and live with their plugin
(see join_template.py / filter_template.py); do not add renderers here.

The module-level TEMPLATE_ID / TEMPLATE_VERSION and the render_join re-export
describe the *default* feature (JOIN), kept for backwards-compatible imports.
"""

from __future__ import annotations

from typing import Any

from xgtest.core.canonical import xgmj1_sha256
from xgtest.generator.join_template import (
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    _expected_rows,
    _literal,
    _matches,
    _relation,
    _source_rows,
    _value,
    render_join,
)


def semantic_hash(case_payload: dict[str, Any]) -> str:
    step_projection = [
        {"sql": step["sql"], "expected": step["expected"], "comparison": step["comparison"]}
        for step in case_payload["steps"]
    ]
    return xgmj1_sha256(step_projection)
