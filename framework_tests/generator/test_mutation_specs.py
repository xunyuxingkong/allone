from dataclasses import dataclass
from pathlib import Path
import json

import pytest

from xgtest.core.evidence_models import MutationCheck
from xgtest.design.model import load_test_model
from xgtest.generator.candidate import generate_candidates, static_validate_candidate
from xgtest.generator import lifecycle
from xgtest.generator.plugins import JoinPlugin, MutationSpec, MutationPolicy, PluginRegistry, mutation_spec_for


@dataclass(frozen=True)
class TwoRulePlugin(JoinPlugin):
    def mutation_specs(self):
        return (MutationSpec("rule_a", "1", lambda _: False, lambda sql: sql + " "),
                MutationSpec("rule_b", "1", lambda _: False, lambda sql: sql + "\n"))


def test_each_required_rule_is_bound_and_missing_duplicate_weak_fail():
    plugin = TwoRulePlugin()
    checks = tuple(MutationCheck(mutation_id=spec.mutation_id, status="NOT_APPLICABLE") for spec in plugin.mutation_specs())
    plugin.mutation_policy.validate(object(), checks, plugin.mutation_specs())
    for invalid in (checks[:1], (checks[0], checks[0]), (checks[0], MutationCheck(mutation_id="unknown", status="NOT_APPLICABLE"))):
        with pytest.raises(ValueError, match="SPEC_SET_MISMATCH"):
            plugin.mutation_policy.validate(object(), invalid, plugin.mutation_specs())
    with pytest.raises(ValueError, match="MUTATION_ID_REQUIRED"):
        mutation_spec_for(plugin)
    assert mutation_spec_for(plugin, "rule_b").mutation_id == "rule_b"
    with pytest.raises(ValueError, match="GATE_FAILED"):
        MutationPolicy().validate(object(), (MutationCheck(mutation_id="required", status="WEAK"),), (MutationSpec("required", "1", lambda _: True, lambda sql: sql),))


def test_multi_rule_execution_and_evidence_do_not_drop_second_rule(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    plugin = TwoRulePlugin()
    monkeypatch.setattr(lifecycle, "FEATURE_PLUGINS", PluginRegistry((plugin,)))
    model = load_test_model(root / "models/query/join.yaml")
    candidate = generate_candidates(model, "pairwise", (), tmp_path / "candidates", limit=1)[0]
    static_validate_candidate(candidate, model)
    profile = {"sql_runtime_profile_id": "a" * 64}
    results = lifecycle.validate_candidate_mutations(candidate, model, object(), profile, runner=lambda *args: pytest.fail("non-applicable rule must not execute"))
    assert {result["mutation_id"] for result in results} == {"rule_a", "rule_b"}
    evidence = lifecycle.record_candidate_mutation_evidence(candidate, results, tmp_path / "mutations", profile)
    artifact = json.loads(Path(evidence["mutation_artifact"]).read_text())
    assert len(artifact["checks"]) == 2 and artifact["executions"] == {}
    assert artifact["spec_versions"] == {"rule_a": "1", "rule_b": "1"}
    checks = tuple(MutationCheck.model_validate(item) for item in artifact["checks"])
    plugin.mutation_policy.validate(object(), checks, plugin.mutation_specs(), artifact=artifact)
    artifact["spec_versions"]["rule_b"] = "2"
    with pytest.raises(ValueError, match="POLICY_VERSION_MISMATCH"):
        plugin.mutation_policy.validate(object(), checks, plugin.mutation_specs(), artifact=artifact)


def test_multi_killed_rules_bind_separate_sql_and_reject_swapped_execution(tmp_path, monkeypatch):
    from xgtest.core.canonical import xgmj1_sha256
    from xgtest.core.execution_models import QueryCaseReport, QueryStepReport
    from xgtest.generated.registry_enums import CaseExecutionStatus, StepStatus
    from xgtest.runtime.comparator import rows_sha256
    from xgtest.query.loader import load_query_case

    @dataclass(frozen=True)
    class ApplicablePlugin(JoinPlugin):
        def mutation_specs(self):
            return tuple(MutationSpec(name, "1", lambda _: True, lambda sql, suffix=name: sql + f" -- {suffix}") for name in ("rule_a", "rule_b"))

    plugin = ApplicablePlugin()
    monkeypatch.setattr(lifecycle, "FEATURE_PLUGINS", PluginRegistry((plugin,)))
    root = Path(__file__).resolve().parents[2]
    model = load_test_model(root / "models/query/join.yaml")
    candidate = generate_candidates(model, "pairwise", (), tmp_path / "candidates", limit=1)[0]
    static_validate_candidate(candidate, model)
    case = load_query_case(candidate)
    def synthetic_report(value, status):
        rows = ((value,),)
        return QueryCaseReport(case_id=case.metadata.id, status=CaseExecutionStatus(status), duration_ms=1,
            steps=(QueryStepReport(id="q1", status=StepStatus(status), duration_ms=1, columns=("k",), column_types=("INTEGER",), logical_types=("int",), row_count=1,
                result_rows=rows, result_sha256=rows_sha256(list(rows), ("INTEGER",), 1)),)).model_dump(mode="json")
    baseline = synthetic_report(1, "PASS")
    results = []
    for index, spec in enumerate(plugin.mutation_specs()):
        mutated = synthetic_report(index + 2, "FAIL")
        results.append({"case_id": case.metadata.id, "mutation_id": spec.mutation_id, "status": "KILLED",
            "original_hash": lifecycle._mutation_result_digest(baseline, case, require_rows=True),
            "mutated_hash": lifecycle._mutation_result_digest(mutated, case, require_rows=True),
            "execution": {"original_sql_sha256": xgmj1_sha256([step.sql for step in case.steps]),
                "mutated_sql_sha256": xgmj1_sha256([spec.rewrite(step.sql) for step in case.steps]),
                "baseline_runs": [baseline, baseline], "mutated_runs": [mutated, mutated],
                "build_observations": [{"query": "SHOW build_time;", "captured_at": "synthetic", "raw_value": "synthetic"}] * 2}})
    evidence = lifecycle.record_candidate_mutation_evidence(candidate, results, tmp_path / "mutations", {"sql_runtime_profile_id": "a" * 64})
    artifact = json.loads(Path(evidence["mutation_artifact"]).read_text())
    assert set(artifact["executions"]) == {"rule_a", "rule_b"}
    assert artifact["execution"] is None
    results[1]["execution"] = results[0]["execution"]
    with pytest.raises(ValueError, match="EXECUTION_SQL_MISMATCH"):
        lifecycle.record_candidate_mutation_evidence(candidate, results, tmp_path / "mutations", {"sql_runtime_profile_id": "a" * 64})
