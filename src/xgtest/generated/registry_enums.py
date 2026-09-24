# Generated from registry/*.yaml; do not edit.
from enum import StrEnum

class CapabilityKey(StrEnum):
    SQL_EXECUTE = "sql.execute"
    SQL_CANCEL = "sql.cancel"
    SESSION_RESET_PROBE = "session.reset_probe"

class FailureType(StrEnum):
    ASSERTION_FAILED = "ASSERTION_FAILED"
    FIXTURE_SETUP = "FIXTURE_SETUP"
    FIXTURE_CLEANUP = "FIXTURE_CLEANUP"
    INFRA_NETWORK = "INFRA_NETWORK"
    INFRA_TIMEOUT = "INFRA_TIMEOUT"
    INFRA_RESOURCE = "INFRA_RESOURCE"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"

class FeatureKey(StrEnum):
    JOIN = "join"
    UNION = "union"
    DDL_TABLE = "ddl_table"
    STRING_FUNCTION = "string_function"
    QUERY = "query"

class IsolationScope(StrEnum):
    SESSION = "session"
    WORKER_SCHEMA = "worker_schema"
    CASE_SCHEMA = "case_schema"
    DATABASE = "database"
    CLUSTER = "cluster"

class Level(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class ResourceAccessMode(StrEnum):
    SHARED_READ = "shared_read"
    SHARED_WRITE = "shared_write"
    EXCLUSIVE = "exclusive"

class AttemptStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"

class CaseAssetStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    REVIEW = "review"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"

class CaseExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    INFRA_RECOVERED = "INFRA_RECOVERED"

class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
