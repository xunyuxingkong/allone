"""Execution models; definitions owned by this layer."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator
from xgtest.generated.registry_enums import (AttemptStatus, CaseAssetStatus, CaseExecutionStatus, FailureType, FeatureKey, IsolationScope, Level, ResourceAccessMode, StepStatus)
from .model_base import StrictModel


class ComparisonProfile(StrictModel):
    mode: Literal["exact", "rowsort", "sha256", "expected_error"]
    canonical_version: Literal["1"] = "1"
    error_profile: str | None = None
    normalization_profile: str | None = None
    float_policy: str = "canonical_ieee754"
    timestamp_policy: str = "rfc3339"



class ExpectedRows(StrictModel):
    rows: tuple[tuple[Any, ...], ...]



class ExpectedHash(StrictModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")



class ExpectedError(StrictModel):
    code: str | None = Field(default=None, min_length=1)
    sqlstate: str | None = Field(default=None, min_length=1)
    message_pattern: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def at_least_one_matcher_required(self) -> "ExpectedError":
        if self.code is None and self.sqlstate is None and self.message_pattern is None:
            raise ValueError("EXPECTED_ERROR_EMPTY: at least one error matcher is required")
        return self



class ExpectedStatement(StrictModel):
    affected_rows: int = Field(ge=0)



TYPED_EXPECTED_VERSION = "1"



def decode_expected(value: dict[str, Any]) -> ExpectedRows | ExpectedHash | ExpectedError | ExpectedStatement:
    """Decode one unambiguous expected variant at the asset boundary."""
    if not isinstance(value, dict):
        raise ValueError("EXPECTED_INVALID: expected must be a mapping")
    variants = (
        ("rows", ExpectedRows),
        ("sha256", ExpectedHash),
        ("affected_rows", ExpectedStatement),
    )
    selected = [model for key, model in variants if key in value]
    if any(key in value for key in ("code", "sqlstate", "message_pattern")):
        selected.append(ExpectedError)
    if len(selected) != 1:
        raise ValueError("EXPECTED_AMBIGUOUS: expected must select exactly one variant")
    model = selected[0]
    if model is ExpectedRows:
        rows = value["rows"]
        if not isinstance(rows, (list, tuple)) or any(not isinstance(row, (list, tuple)) for row in rows):
            raise ValueError("EXPECTED_ROWS_INVALID: rows must be a list of rows")
        return ExpectedRows.model_validate({**value, "rows": tuple(tuple(row) for row in rows)})
    return model.model_validate(value)



class SqlStep(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    kind: Literal["setup", "statement", "query", "cleanup"]
    sql: str = Field(min_length=1)
    comparison: ComparisonProfile | None = None
    expected: ExpectedRows | ExpectedHash | ExpectedError | ExpectedStatement | None = None



_QUERY_MUTATION_KEYWORDS = {
    "ALTER", "CALL", "COMMIT", "CREATE", "DELETE", "DO", "DROP", "EXEC", "EXECUTE",
    "GRANT", "IMPORT", "INSERT", "LOCK", "LOAD", "MERGE", "NEXTVAL", "REPLACE",
    "RESET", "REVOKE", "ROLLBACK", "SAVEPOINT", "SET", "SETVAL", "TRUNCATE", "UNLOCK",
    "UPDATE", "UPSERT", "VACUUM", "INTO",
}



def _query_sql_tokens(sql: str) -> tuple[str, ...]:
    """Return executable SQL words while ignoring quoted text and comments."""
    code: list[str] = []
    index = 0
    while index < len(sql):
        char = sql[index]
        following = sql[index + 1] if index + 1 < len(sql) else ""
        if char == "-" and following == "-":
            newline = sql.find("\n", index + 2)
            index = len(sql) if newline < 0 else newline + 1
            code.append(" ")
            continue
        if char == "/" and following == "*":
            end = sql.find("*/", index + 2)
            if end < 0:
                raise ValueError("QUERY_SQL_NOT_READ_ONLY: unterminated comment")
            index = end + 2
            code.append(" ")
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            while index < len(sql):
                if sql[index] == quote:
                    if index + 1 < len(sql) and sql[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            else:
                raise ValueError("QUERY_SQL_NOT_READ_ONLY: unterminated quoted text")
            code.append(" ")
            continue
        if char == "[":
            end = sql.find("]", index + 1)
            if end < 0:
                raise ValueError("QUERY_SQL_NOT_READ_ONLY: unterminated quoted identifier")
            index = end + 1
            code.append(" ")
            continue
        if char == ";":
            raise ValueError("QUERY_SQL_NOT_READ_ONLY: multiple statements are not allowed")
        code.append(char)
        index += 1
    return tuple(re.findall(r"[A-Za-z_][A-Za-z0-9_$]*", "".join(code).upper()))



def _validate_read_only_query_sql(sql: str) -> str:
    """Reject obvious writes at the typed boundary; DB privileges remain authoritative."""
    tokens = _query_sql_tokens(sql)
    if not tokens or tokens[0] not in {"SELECT", "WITH"}:
        raise ValueError("QUERY_SQL_NOT_READ_ONLY: only SELECT queries are allowed")
    mutation = next((token for token in tokens if token in _QUERY_MUTATION_KEYWORDS), None)
    if mutation is not None:
        raise ValueError(f"QUERY_SQL_NOT_READ_ONLY: forbidden SQL keyword {mutation}")
    return sql



class QueryStep(SqlStep):
    kind: Literal["query"] = "query"
    comparison: ComparisonProfile
    expected: ExpectedRows | ExpectedHash | ExpectedError

    @field_validator("sql")
    @classmethod
    def sql_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("QUERY_SQL_EMPTY")
        return _validate_read_only_query_sql(value)

    @model_validator(mode="after")
    def expected_variant_matches_mode(self) -> "QueryStep":
        if self.comparison.mode == "expected_error" and not isinstance(self.expected, ExpectedError):
            raise ValueError("QUERY_EXPECTED_MODE_MISMATCH: expected_error requires ExpectedError")
        if self.comparison.mode != "expected_error" and isinstance(self.expected, ExpectedError):
            raise ValueError("QUERY_EXPECTED_MODE_MISMATCH: ExpectedError requires expected_error mode")
        if self.comparison.mode == "sha256" and not isinstance(self.expected, ExpectedHash):
            raise ValueError("QUERY_EXPECTED_MODE_MISMATCH: sha256 requires ExpectedHash")
        if self.comparison.mode != "sha256" and isinstance(self.expected, ExpectedHash):
            raise ValueError("QUERY_EXPECTED_MODE_MISMATCH: ExpectedHash requires sha256 mode")
        return self



class RuntimeTargetIdentity(StrictModel):
    """Stable target semantics used to derive a runtime profile ID."""

    database_product: str | None = None
    database_version: str | None = None
    db_build: str | None = None
    driver_name: str | None = None
    driver_version: str | None = None
    os: str | None = None
    arch: str | None = None
    topology: str | None = None
    mode: str | None = None
    configuration_fingerprint: str | None = None
    dataset_fingerprint: str | None = None



class RuntimeDriverIdentity(StrictModel):
    """Stable driver/runtime fields; probe details remain evidence only."""

    module: str | None = None
    version: list[int | str] | tuple[int | str, ...] | str | None = None
    build: str | None = None
    python_version: list[int | str] | tuple[int | str, ...] | str | None = None



class TypeMappingProfile(StrictModel):
    status: str | None = None
    operation_status: str | None = None
    mapping_status: str | None = None
    canonical_compatibility: str | bool | None = None
    mapping_fidelity: Literal["EXACT", "LOSSY", "AMBIGUOUS", "UNKNOWN"] | None = None
    canonical_encoding: Literal["VERIFIED", "FAILED", "UNKNOWN"] | None = None
    support_status: Literal["SUPPORTED", "UNSUPPORTED"] | None = None
    logical_type: str | None = None



class TransactionSemantics(StrictModel):
    status: str | None = None
    autocommit_disabled: bool | None = None
    commit_visible: bool | None = None
    rollback_visible: bool | None = None



class ErrorMappingProfile(StrictModel):
    status: str | None = None
    exception_type: str | None = None
    code: str | None = None
    sqlstate: str | None = None



class CapabilityOutcome(StrictModel):
    status: str | None = None
    driver_has_cancel: bool | None = None



class RuntimeCapabilitiesIdentity(StrictModel):
    connection: CapabilityOutcome | None = None
    type_mapping: dict[str, TypeMappingProfile] | None = None
    transaction_commit_rollback: TransactionSemantics | None = None
    sql_error_mapping: ErrorMappingProfile | None = None
    cancel_stop_proof: CapabilityOutcome | None = None
    reset_probe: CapabilityOutcome | None = None



class RuntimeProfileIdentity(StrictModel):
    """Structured semantic projection hashed into ``sql_runtime_profile_id``."""

    profile_schema_version: Literal["0.2"]
    target: RuntimeTargetIdentity
    driver: RuntimeDriverIdentity
    capabilities: RuntimeCapabilitiesIdentity
    contract_set_id: str | None = None



class RuntimeProfile(StrictModel):
    """Published, validated SQL runtime profile envelope."""

    profile_schema_version: Literal["0.2"]
    identity: RuntimeProfileIdentity
    target: dict[str, str]
    driver: dict[str, Any]
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sql_runtime_profile_id: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def profile_id_must_match_identity(self) -> "RuntimeProfile":
        import hashlib

        from xgtest.core.canonical import xgmj1_bytes

        identity = self.identity.model_dump(mode="python", exclude_none=True)
        expected = hashlib.sha256(xgmj1_bytes(identity)).hexdigest()
        if self.sql_runtime_profile_id != expected:
            raise ValueError("RUNTIME_PROFILE_ID_MISMATCH: profile identity does not match")
        return self



class MvpStepReport(StrictModel):
    id: str
    kind: str
    status: StepStatus
    duration_ms: float = Field(ge=0)
    columns: tuple[str, ...] = ()
    column_types: tuple[str | None, ...] = ()
    logical_types: tuple[str | None, ...] = ()
    rows: tuple[tuple[Any, ...], ...] = ()
    affected_rows: int | None = None
    error_type: str | None = None
    error_code: str | None = None
    sqlstate: str | None = None
    error: str | None = None



class MvpCaseReport(StrictModel):
    case_id: str
    status: CaseExecutionStatus
    primary_status: CaseExecutionStatus
    cleanup_status: Literal["PASS", "FAILED"]
    recovery_status: Literal["PASS", "FAILED"]
    failure_type: FailureType | None = None
    duration_ms: float = Field(ge=0)
    steps: tuple[MvpStepReport, ...]
    error: str | None = None



class MvpTargetReport(StrictModel):
    """Typed target context emitted by the bootstrap runner."""

    database_alias: str
    host_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    sql_runtime_profile_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")



class MvpRunReport(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    started_at: datetime
    finished_at: datetime
    target: MvpTargetReport
    cases: tuple[MvpCaseReport, ...]
    status: CaseExecutionStatus



class QueryStepReport(StrictModel):
    id: str
    status: StepStatus
    duration_ms: float = Field(ge=0)
    columns: tuple[str, ...] = ()
    column_types: tuple[str | None, ...] = ()
    logical_types: tuple[str | None, ...] = ()
    row_count: int | None = Field(default=None, ge=0)
    result_rows: tuple[tuple[Any, ...], ...] | None = None
    result_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    error_type: str | None = None
    error_code: str | None = None
    sqlstate: str | None = None
    error: str | None = None

    @field_validator("result_rows", mode="before")
    @classmethod
    def decode_observed_rows(cls, value: Any) -> Any:
        if value is None:
            return None
        # Python driver values are already typed; only tagged JSON cells need decoding.
        from .row_codec import decode_cell
        if not isinstance(value, (list, tuple)) or any(not isinstance(row, (list, tuple)) for row in value):
            raise ValueError("ROW_CODEC_ROWS_INVALID")
        return tuple(tuple(decode_cell(cell) if isinstance(cell, dict) else cell for cell in row) for row in value)

    @field_serializer("result_rows", when_used="json")
    def encode_observed_rows(self, value: Any) -> Any:
        from .row_codec import encode_rows
        return None if value is None else encode_rows(value)



class QueryCaseReport(StrictModel):
    case_id: str
    title: str | None = None
    feature: str | None = None
    tags: tuple[str, ...] = ()
    source_file: str | None = None
    case_source_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    status: CaseExecutionStatus
    failure_type: FailureType | None = None
    duration_ms: float = Field(ge=0)
    steps: tuple[QueryStepReport, ...]
    error: str | None = None

    @field_validator("source_file")
    @classmethod
    def source_file_must_be_relative(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.startswith(("/", "\\")) or "\\" in value or ":" in value or ".." in value.split("/"):
            raise ValueError("source_file must be repository-relative")
        return value



class QueryTargetReport(StrictModel):
    database_alias: str
    host_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    sql_runtime_profile_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    contract_set_id: str = Field(pattern=r"^[0-9a-f]{64}$")



class QueryRunReport(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    started_at: datetime
    finished_at: datetime
    target: QueryTargetReport
    git_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40,64}$")
    cases: tuple[QueryCaseReport, ...]
    status: CaseExecutionStatus



class ExecutableMetadata(StrictModel):
    id: str
    timeout: str


class QueryExecutable(StrictModel):
    schema_version: str = "1"
    metadata: ExecutableMetadata
    steps: tuple[QueryStep, ...]

    @property
    def execution_hash(self) -> str:
        from .canonical import xgmj1_sha256
        return xgmj1_sha256(self.model_dump(mode="json"))
