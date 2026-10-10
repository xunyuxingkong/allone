"""AI Exploratory briefing: tell the agent what is uncovered and at what risk.

This is a read-only analysis over Core coverage and the durable job's recorded
results. It never generates cases, changes status or decides truth; the external
agent reads the briefing and chooses the next action. The risk classification is
a transparent heuristic over model dimension/value names, not a new oracle.
"""

from __future__ import annotations

from typing import Any

# Risk buckets and the substrings that map a dimension/value name onto them.
# Order matters: the first matching bucket wins for each dimension. Structural
# dimension names are listed first so e.g. `join_type` is not captured by the
# `type` needle in type_conversion.
_RISK_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("structure", ("join_type", "interaction", "grouping", "correlation", "predicate", "function", "composition")),
    ("null", ("null",)),
    ("duplicate", ("duplicate", "cardinality")),
    ("boundary", ("less", "greater", "between", "boundary", "limit", "offset", "direction", "ordering")),
    ("type_conversion", ("conversion", "datatype", "cast")),
)


def classify_risk(selections: dict[str, str]) -> list[str]:
    """Map a coverage requirement's selections onto explainable risk buckets."""
    risks: set[str] = set()
    for dimension, value in sorted(selections.items()):
        token = f"{dimension}_{value}".lower()
        for risk, needles in _RISK_PATTERNS:
            if any(needle in token for needle in needles):
                risks.add(risk)
                break
    return sorted(risks) or ["general"]


def gap_by_risk(missing_requirements: list[dict]) -> list[dict]:
    """Group uncovered requirements by risk, largest first, with representative examples."""
    buckets: dict[str, list[dict]] = {}
    for item in missing_requirements:
        selections = dict(item.get("selections", {}))
        for risk in classify_risk(selections):
            buckets.setdefault(risk, []).append(selections)
    return [
        {
            "risk": risk,
            "missing": len(items),
            "examples": [
                " · ".join(f"{k}={v}" for k, v in sorted(example.items()))
                for example in items[:3]
            ],
        }
        for risk, items in sorted(buckets.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    ]


def brief(coverage: dict[str, Any], failures: list[dict], generated_rounds: int) -> dict[str, Any]:
    """Assemble the exploration briefing the external agent reasons over."""
    missing = coverage.get("missing_requirements", []) or []
    risks = gap_by_risk(missing)
    total = coverage.get("required", 0)
    covered = coverage.get("active_covered", 0)
    blocks = []
    if missing:
        blocks.append({"kind": "coverage", "risk": risks[0]["risk"],
                       "detail": f"最高风险区域仍有 {risks[0]['missing']} 项未覆盖", "examples": risks[0]["examples"]})
    for failure in failures[:5]:
        blocks.append({"kind": "failure", "risk": "failure",
                       "detail": f"{failure.get('case_id')} {failure.get('failure_type') or failure.get('status')}",
                       "examples": []})
    if not blocks:
        blocks.append({"kind": "complete", "risk": "none",
                       "detail": "当前定义范围已无缺口，可进入验收或扩展新的测试范围", "examples": []})
    return {
        "required": total,
        "covered": covered,
        "missing": coverage.get("active_missing", 0),
        "coverage_ratio": round(covered / total, 4) if total else None,
        "risk_areas": risks,
        "failures": failures,
        "exploration_rounds": generated_rounds,
        "suggestions": blocks,
        "advisory_only": True,
        "does_not_change_core": True,
    }
