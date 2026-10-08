"""Four application services; all testing and admission decisions delegate to Core."""
import hashlib
import json
import os
import subprocess
import sys
import uuid
from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path
import yaml

from xgtest.ai.models import ActionResult, TechnicalReview
from xgtest.ai.store import write_json
from xgtest.core.canonical import xgmj1_sha256
from xgtest.core.contract_set import build_contract_descriptor
from xgtest.core.asset_lock import active_asset_lock
from xgtest.core.execution_models import QueryRunReport
from xgtest.generator.plugins import FEATURE_PLUGINS, mutation_specs_for
from xgtest.generator.lifecycle import _validate_mutation_execution, _write_payload
from xgtest.generator.package import freeze_pre_promotion_manifest, verify_pre_promotion_package, preflight_promotion, build_promotion_plan
from xgtest.generator.promotion_batch import execute_promotion_batch
from xgtest.generator.post_acceptance import freeze_post_promotion_package, verify_post_promotion_package, generate_final_acceptance
from xgtest.generator.scope import resolve_scope
from xgtest.generator.template import semantic_hash
from xgtest.query.loader import load_query_case, load_query_directory_with_sources
from xgtest.runtime.profile import load_profile
from xgtest.web.service import QueryReadService


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_hash(context):
    return xgmj1_sha256(json.loads(json.dumps(context), parse_float=Decimal))


@dataclass
class ServiceContext:
    root: Path
    job_dir: Path
    profile_path: Path
    approval_path: Path | None = None
    allowed_signers_path: Path | None = None
    revoked_path: Path | None = None

    def __post_init__(self):
        self.root = self.root.resolve()
        self.job_dir = self.job_dir.resolve()
        self.profile_path = self.profile_path.resolve()
        if not self.job_dir.is_relative_to((self.root / "artifacts/jobs").resolve()) or not self.profile_path.is_relative_to(self.root):
            raise ValueError("SERVICE_PATH_INVALID")
        self.scope = resolve_scope()
        self.reader = QueryReadService(self.root / "artifacts/runs", self.scope.path(self.root, "active_suite_root"), project_root=self.root, profile_path=self.profile_path)

    def relative(self, path):
        return path.resolve().relative_to(self.root).as_posix()

    def candidate(self, case_id):
        import re
        if not re.fullmatch(r"QUERY\.JOIN\.[A-Z0-9]+", case_id):
            raise ValueError("CANDIDATE_ID_INVALID")
        path = (self.scope.path(self.root, "candidate_root") / f"{case_id}.yaml").resolve()
        if not path.is_relative_to(self.scope.path(self.root, "candidate_root")):
            raise ValueError("CANDIDATE_PATH_INVALID")
        return path


class DatabaseExecutor:
    """Fixed operations only. Credentials stay in the environment, out of job files."""
    def execute(self, ctx, operation, case_id=None):
        keys = ("XGTEST_DB_HOST", "XGTEST_DB_PORT", "XGTEST_DB_NAME", "XGTEST_DB_USER", "XGTEST_DB_PASSWORD")
        if any(not os.environ.get(key) for key in keys):
            return {"status": "BLOCKED", "error": "DATABASE_CONFIG_MISSING"}
        directory = ctx.job_dir / "executions" / uuid.uuid4().hex
        request = directory / "request.json"
        write_json(request, {"operation": operation, "case_id": case_id, "profile": ctx.relative(ctx.profile_path), "directory": ctx.relative(directory)})
        backend = os.environ.get("XGTEST_DB_EXECUTOR", "native")
        if backend == "wsl" and os.name == "nt":
            command = ["wsl", "--exec", "env", "PYTHONPATH=artifacts/wsl-runtime/site:artifacts/wsl-runtime/driver:src",
                       *(f"{key}={os.environ[key]}" for key in keys), "timeout", "600", "python3", "-m", "xgtest.application.db_worker", ctx.relative(request)]
        elif backend == "native":
            command = [sys.executable, "-m", "xgtest.application.db_worker", ctx.relative(request)]
        else:
            return {"status": "BLOCKED", "error": "DATABASE_EXECUTOR_UNSUPPORTED"}
        try:
            completed = subprocess.run(command, cwd=ctx.root, capture_output=True, timeout=610, check=False)
            result_path = request.with_suffix(".result.json")
            if completed.returncode or not result_path.is_file():
                return {"status": "BLOCKED", "error": "DATABASE_WORKER_FAILED"}
            result = read_json(result_path)
            result["directory"] = ctx.relative(directory)
            return result
        except (OSError, subprocess.TimeoutExpired):
            return {"status": "BLOCKED", "error": "DATABASE_WORKER_UNAVAILABLE"}


class ProjectService:
    def __init__(self, ctx, db): self.ctx, self.db = ctx, db

    def inspect(self):
        cid = build_contract_descriptor(self.ctx.root)["contract_set_id"]
        blockers = []
        profile_id = None
        try:
            profile = load_profile(self.ctx.profile_path)
            profile_id = profile["sql_runtime_profile_id"]
            if profile["identity"].get("contract_set_id") != cid:
                blockers.append("RUNTIME_PROFILE_STALE")
        except (OSError, ValueError):
            blockers.append("RUNTIME_PROFILE_UNAVAILABLE")
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.ctx.root, capture_output=True, check=False)
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=self.ctx.root, capture_output=True, check=False)
        return {"ready": not blockers, "database": "Xugu", "execution_contract_id": cid, "runtime_profile_id": profile_id,
                "git_commit": commit.stdout.decode().strip(), "source_dirty": bool(dirty.stdout), "blockers": blockers}

    def preflight(self):
        state = self.inspect()
        if state["blockers"]:
            return ActionResult(action="project.preflight", status="BLOCKED", outputs=state, blockers=state["blockers"])
        result = self.db.execute(self.ctx, "preflight")
        return ActionResult(action="project.preflight", status="PASS" if result["status"] == "PASS" else "BLOCKED", outputs={**result, "project_identity": state},
                            blockers=[] if result["status"] == "PASS" else [result.get("error", "DATABASE_PREFLIGHT_FAILED")])


class ModuleService:
    def __init__(self, ctx, db): self.ctx, self.db = ctx, db

    def input_identity(self):
        return xgmj1_sha256({"assets": {self.ctx.relative(path): sha(path) for path in self.ctx.scope.asset_paths(self.ctx.root, "active_suite_root")},
                            "execution_contract_id": build_contract_descriptor(self.ctx.root)["contract_set_id"],
                            "runtime_profile_id": load_profile(self.ctx.profile_path)["sql_runtime_profile_id"]})

    def inspect(self, module_id="query"):
        if module_id != "query": raise ValueError("MODULE_UNSUPPORTED")
        coverage = self.ctx.reader.coverage()
        return {"module": "query", "features": {"join": coverage}, "module_completion": "MODULE_FULL_INCOMPLETE",
                "active_input_identity": self.input_identity(), "candidates": self.ctx.reader.list_candidates()["items"]}

    def run_regression(self, module_id="query"):
        if module_id != "query": raise ValueError("MODULE_UNSUPPORTED")
        before = self.input_identity()
        result = self.db.execute(self.ctx, "regression")
        status = result["status"] if result["status"] in {"PASS", "FAIL", "BLOCKED"} else "FAIL"
        if before != self.input_identity(): status = "BLOCKED"
        refs = [f"{result['directory']}/{name}" for name in ("regression.json", "regression-build.json") if result.get("directory") and (self.ctx.root / result["directory"] / name).is_file()]
        return ActionResult(action="module.regression", status=status, outputs={**result, "input_identity": before, "artifact_hashes": {ref: sha(self.ctx.root / ref) for ref in refs}},
                            evidence_refs=refs, blockers=[] if status == "PASS" else [result.get("error", "REGRESSION_FAILED_OR_INPUT_CHANGED")])

    def regression_valid(self, result):
        try:
            if result.status != "PASS" or result.outputs["input_identity"] != self.input_identity(): return False
            if len(result.evidence_refs) != 2 or set(result.outputs["artifact_hashes"]) != set(result.evidence_refs): return False
            for ref, digest in result.outputs["artifact_hashes"].items():
                if sha(self.ctx.root / ref) != digest: return False
            path = self.ctx.root / result.evidence_refs[0]
            report = QueryRunReport.model_validate_json(path.read_bytes())
            expected = {asset.case.metadata.id: asset for asset in load_query_directory_with_sources(self.ctx.scope.path(self.ctx.root, "active_suite_root"))}
            return report.status.value == "PASS" and len(report.cases) == len(expected) and {case.case_id for case in report.cases} == set(expected) and all(
                case.status.value == "PASS" and case.case_source_hash == expected[case.case_id].source.source_hash
                for case in report.cases)
        except (ValueError, OSError, KeyError, IndexError): return False

    def inspect_coverage(self, feature_id="query.join"):
        if feature_id != "query.join": raise ValueError("FEATURE_UNSUPPORTED")
        return ActionResult(action="feature.coverage", status="PASS", outputs=self.ctx.reader.coverage())


class CandidateService:
    def __init__(self, ctx, db): self.ctx, self.db = ctx, db

    def mutation_valid(self, case_id):
        try:
            path = self.ctx.candidate(case_id); case = load_query_case(path); evidence = case.mutation_evidence
            if evidence is None: return False
            profile = load_profile(self.ctx.profile_path)
            if (evidence.semantic_hash != semantic_hash(yaml.safe_load(path.read_text(encoding="utf-8")))
                or evidence.runtime_profile_id != profile["sql_runtime_profile_id"]
                or evidence.contract_set_id != build_contract_descriptor(self.ctx.root)["contract_set_id"]): return False
            artifact = json.loads(self.ctx.reader.candidate_artifact(case_id, "mutation"))
            if any(artifact.get(key) != value for key, value in {"case_id": case_id, "semantic_hash": evidence.semantic_hash,
                "runtime_profile_id": evidence.runtime_profile_id, "contract_set_id": evidence.contract_set_id,
                "checks": [check.model_dump(mode="json") for check in evidence.checks]}.items()): return False
            plugin = FEATURE_PLUGINS.for_case(case)
            plugin.mutation_policy.validate(case, evidence.checks, mutation_specs_for(plugin), artifact=artifact)
            target = profile["identity"]["target"]
            for check in evidence.checks:
                if check.status == "KILLED":
                    executions = artifact.get("executions")
                    execution = executions.get(check.mutation_id) if isinstance(executions, dict) else artifact.get("execution") if len(evidence.checks) == 1 else None
                    _validate_mutation_execution(case, execution, check.original_hash, check.mutated_hash,
                        f"{target.get('db_build', '')} {target.get('database_version', '')}".strip(), mutation_id=check.mutation_id)
            return True
        except (ValueError, OSError, KeyError, TypeError): return False

    def readiness(self):
        items = []
        for item in self.ctx.reader.list_candidates()["items"]:
            case_id = item["case_id"]; case = load_query_case(self.ctx.candidate(case_id))
            static = False
            if case.metadata.status.value in {"draft", "review"}:
                try:
                    FEATURE_PLUGINS.for_case(case).static_validate(self.ctx.candidate(case_id), self.ctx.scope.load_model(self.ctx.root)); static = True
                except ValueError: pass
            items.append({**item, "static_valid": static, "mutation_valid": self.mutation_valid(case_id), "technical_review_valid": self.review_valid(case_id)})
        return items

    def generate(self):
        model = self.ctx.scope.load_model(self.ctx.root)
        assets = load_query_directory_with_sources(self.ctx.scope.path(self.ctx.root, "active_suite_root"))
        feature_root = self.ctx.scope.path(self.ctx.root, "active_root")
        legacy = set(self.ctx.scope.legacy_feature_assets)
        cases = tuple(asset.case for asset in assets if (self.ctx.scope.path(self.ctx.root, "active_suite_root") / asset.source.relative_path).resolve().is_relative_to(feature_root)
                      or self.ctx.relative(self.ctx.scope.path(self.ctx.root, "active_suite_root") / asset.source.relative_path) in legacy)
        with active_asset_lock(self.ctx.root, publishing=True):
            paths = FEATURE_PLUGINS.for_model(model.model_id).generate(model, self.ctx.scope.coverage_strategy, cases, self.ctx.scope.path(self.ctx.root, "candidate_root"))
        return ActionResult(action="candidate.generate", status="PASS", outputs={"candidate_ids": [load_query_case(path).metadata.id for path in paths]})

    def validate(self, case_id):
        result = FEATURE_PLUGINS.for_model(self.ctx.scope.model_id).static_validate(self.ctx.candidate(case_id), self.ctx.scope.load_model(self.ctx.root))
        return ActionResult(action="candidate.validate", case_id=case_id, status="PASS", outputs=result)

    def _draft(self, case_id):
        path = self.ctx.candidate(case_id); payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if payload.get("review_evidence") or payload.get("coverage_review"):
            raise ValueError("HUMAN_REVIEW_REVALIDATION_REQUIRED")
        # Only lifecycle status changes; Core validates semantic/static inputs first.
        self.validate(case_id)
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["metadata"]["status"] = "draft"
        _write_payload(path, payload)

    def mutation_validate(self, case_id):
        if self.mutation_valid(case_id): return ActionResult(action="candidate.mutation", case_id=case_id, status="SKIPPED", outputs={"reason": "VALID_EVIDENCE_REUSED"})
        had_trial = self.ctx.reader.get_candidate(case_id)["trial_evidence_status"] == "verified"
        self._draft(case_id)
        result = self.db.execute(self.ctx, "mutation", case_id)
        if had_trial and result["status"] == "PASS":
            payload = yaml.safe_load(self.ctx.candidate(case_id).read_text(encoding="utf-8")); payload["metadata"]["status"] = "review"; _write_payload(self.ctx.candidate(case_id), payload)
        return ActionResult(action="candidate.mutation", case_id=case_id, status=result["status"], outputs=result,
                            blockers=[] if result["status"] == "PASS" else [result.get("error", "MUTATION_FAILED")])

    def trial(self, case_id):
        if self.ctx.reader.get_candidate(case_id)["trial_evidence_status"] == "verified":
            return ActionResult(action="candidate.trial", case_id=case_id, status="SKIPPED", outputs={"reason": "VALID_EVIDENCE_REUSED"})
        self._draft(case_id)
        result = self.db.execute(self.ctx, "trial", case_id)
        return ActionResult(action="candidate.trial", case_id=case_id, status=result["status"], outputs=result,
                            blockers=[] if result["status"] == "PASS" else [result.get("error", "TRIAL_FAILED")])

    def review_context(self, case_id):
        candidate = yaml.safe_load(self.ctx.candidate(case_id).read_text(encoding="utf-8"))
        for key in ("review_evidence", "coverage_review", "coverage_contribution"):
            candidate.pop(key, None)
        candidate["metadata"].pop("status", None)
        return {"candidate": candidate, "trial": json.loads(self.ctx.reader.candidate_artifact(case_id, "trial")),
                "mutation": json.loads(self.ctx.reader.candidate_artifact(case_id, "mutation")), "runtime_profile": load_profile(self.ctx.profile_path)}

    def review_valid(self, case_id):
        path = self.ctx.job_dir / "technical-reviews" / f"{case_id}.json"
        try:
            payload = read_json(path)
            TechnicalReview.model_validate(payload["review"])
            return payload["input_hash"] == context_hash(self.review_context(case_id))
        except (ValueError, OSError, KeyError, TypeError): return False

    def technical_review(self, case_id, review, expected_context_id):
        if not self.mutation_valid(case_id) or self.ctx.reader.get_candidate(case_id)["trial_evidence_status"] != "verified":
            return ActionResult(action="candidate.technical_review", case_id=case_id, status="BLOCKED", blockers=["CANDIDATE_EVIDENCE_INVALID"])
        context = self.review_context(case_id)
        if context_hash(context) != expected_context_id:
            raise ValueError("TECHNICAL_REVIEW_CONTEXT_STALE")
        review = TechnicalReview.model_validate(review.model_dump(mode="json"))
        path = self.ctx.job_dir / "technical-reviews" / f"{case_id}.json"
        write_json(path, {"input_hash": context_hash(context), "review": review.model_dump(mode="json")})
        return ActionResult(action="candidate.technical_review", case_id=case_id, status="PASS", outputs={"ai_technical_review": review.model_dump(mode="json"), "does_not_satisfy_human_gate": True}, evidence_refs=[self.ctx.relative(path)])


class AcceptanceService:
    def __init__(self, ctx): self.ctx = ctx

    @property
    def directory(self): return self.ctx.job_dir / "acceptance"

    @property
    def manifest_path(self): return self.directory / "package-manifest.json"

    def freeze(self):
        ctx = self.ctx; self.directory.mkdir(parents=True, exist_ok=True)
        trial, mutation = [], []
        for item in ctx.reader.list_candidates()["items"]:
            case = load_query_case(ctx.candidate(item["case_id"]))
            if case.metadata.status.value != "review" or case.validation_evidence is None or case.mutation_evidence is None:
                raise ValueError("CANDIDATE_EVIDENCE_INCOMPLETE")
            ve, me = case.validation_evidence, case.mutation_evidence
            raw = json.loads(ctx.reader.candidate_artifact(case.metadata.id, "trial"))
            trial.append({"case_id": case.metadata.id, "candidate_path": ctx.relative(ctx.candidate(case.metadata.id)),
                "raw_result_rows": True,
                **{f"{run}_row_count": sum(len(step.get("result_rows") or []) for step in raw[run]["steps"]) for run in ("run1", "run2")},
                "artifact_root": "artifacts/trial-runs", "artifact_ref": ve.trial_run_ref, "artifact_sha256": ve.trial_artifact_sha256,
                "semantic_hash": ve.semantic_hash, "trial_result_hash": ve.trial_run_hash, "status": "PASS", "contract_set_id": raw["contract_set_id"],
                "runtime_profile_id": raw["runtime_profile_id"], "database_version": raw["database_version"], "database_build_time": raw["database_build_time"]})
            checks = [check.model_dump(mode="json") for check in me.checks]
            mutation.append({"case_id": case.metadata.id, "semantic_hash": me.semantic_hash, "contract_set_id": me.contract_set_id,
                "runtime_profile_id": me.runtime_profile_id, "artifact_ref": me.artifact_ref, "artifact_sha256": me.artifact_sha256,
                "status": "KILLED" if any(check.status == "KILLED" for check in me.checks) else "NOT_APPLICABLE",
                **(checks[0] if len(checks) == 1 else {"checks": checks})})
        profile = load_profile(ctx.profile_path); target = profile["identity"]["target"]
        write_json(self.directory / "trial-run-index.json", {"candidates": trial, "candidate_count": len(trial), "double_run_pass_count": len(trial), "contract_set_id": profile["identity"]["contract_set_id"],
            "runtime_profile_id": profile["sql_runtime_profile_id"], "database_version": target.get("database_version"), "database_build_time": target.get("db_build")})
        write_json(self.directory / "mutation-validation-index.json", {"candidates": mutation, "candidate_count": len(mutation)})
        coverage = ctx.reader.coverage()
        write_json(self.directory / "coverage-summary.json", {"active_covered": coverage["active_covered"], "active_missing": coverage["active_missing"],
            "required": coverage["required"], "provisional_covered_if_promoted": coverage["provisional_covered"], "provisional_missing_if_promoted": coverage["provisional_missing"], "review_candidate_count": coverage["review_candidate_count"]})
        policy = ctx.root / "acceptance/query-generation-mvp/governance-policy.json"
        if policy.is_file(): write_json(self.directory / "governance-policy.json", read_json(policy))
        write_json(self.manifest_path, freeze_pre_promotion_manifest(ctx.root, self.directory, ctx.profile_path))
        write_json(self.directory / "promotion-plan.json", build_promotion_plan(ctx.root, self.manifest_path))

    def inspect(self):
        self.freeze()
        result = verify_pre_promotion_package(self.ctx.root, self.directory, self.ctx.profile_path, self.manifest_path)
        status = "WAITING_APPROVAL" if result["package_integrity"] == "PASS" else "BLOCKED"
        return ActionResult(action="acceptance.inspect", status=status, outputs=result,
            evidence_refs=[self.ctx.relative(self.manifest_path), self.ctx.relative(self.directory / "promotion-plan.json")],
            blockers=["HUMAN_REVIEW_AND_SIGNED_APPROVAL_REQUIRED"] if status == "WAITING_APPROVAL" else ["PACKAGE_INTEGRITY_FAILED"])

    def preflight(self):
        ctx = self.ctx
        if ctx.approval_path is None or ctx.allowed_signers_path is None:
            return ActionResult(action="acceptance.preflight", status="WAITING_APPROVAL", blockers=["SIGNED_APPROVAL_NOT_CONFIGURED"])
        result = preflight_promotion(ctx.root, self.directory, ctx.profile_path, self.manifest_path,
            approval_path=ctx.approval_path, allowed_signers_path=ctx.allowed_signers_path, revoked_path=ctx.revoked_path)
        valid = result["package_integrity"] == "PASS" and result["readiness"] == "READY" and not result["blockers"]
        return ActionResult(action="acceptance.preflight", status="PASS" if valid else "WAITING_APPROVAL", outputs=result,
            blockers=[] if valid else ["HUMAN_GATE_INCOMPLETE"])

    def promote(self):
        ctx = self.ctx
        if ctx.approval_path is None or ctx.allowed_signers_path is None:
            return ActionResult(action="acceptance.promote", status="WAITING_APPROVAL", blockers=["SIGNED_APPROVAL_NOT_CONFIGURED"])
        # Core performs both initial preflight and signed journal recovery atomically.
        result = execute_promotion_batch(ctx.root, self.directory, ctx.profile_path, self.manifest_path,
            ctx.approval_path, ctx.allowed_signers_path, revoked_path=ctx.revoked_path)
        write_json(self.directory / "promotion-result.json", result)
        return ActionResult(action="acceptance.promote", status="PASS", outputs=result, evidence_refs=[ctx.relative(Path(result["receipt"]))])

    def post_verify(self, regression):
        ctx = self.ctx; result = read_json(self.directory / "promotion-result.json")
        directory = ctx.root / regression.outputs["directory"]
        package = freeze_post_promotion_package(ctx.root, candidate_manifest=self.manifest_path, receipt=Path(result["receipt"]),
            regression=directory / "regression.json", regression_build=directory / "regression-build.json", runtime_profile=ctx.profile_path, approval=ctx.approval_path)
        package_path = self.directory / "post-package.json"; write_json(package_path, package)
        verified = verify_post_promotion_package(ctx.root, package_path, allowed_signers_path=ctx.allowed_signers_path, revoked_path=ctx.revoked_path)
        final = generate_final_acceptance(ctx.root, package_path, allowed_signers_path=ctx.allowed_signers_path, revoked_path=ctx.revoked_path,
            policy_path=self.directory / "governance-policy.json", release_checks_path=ctx.root / "acceptance/query-generation-mvp/release-checks-v14.json")
        write_json(self.directory / "final-acceptance.json", final)
        return ActionResult(action="acceptance.post_verify", status="PASS" if verified["package_integrity"] == "PASS" else "FAIL", outputs={"post": verified, "formal_final": final},
            evidence_refs=[ctx.relative(package_path), ctx.relative(self.directory / "final-acceptance.json")], blockers=[item["code"] for item in verified.get("errors", [])])
