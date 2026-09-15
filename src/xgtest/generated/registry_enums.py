# Generated from registry/*.yaml; do not edit.
from enum import StrEnum

class Capabilities(StrEnum):
    SQL_EXECUTE = "sql.execute"
    SQL_CANCEL = "sql.cancel"
    SESSION_RESET_PROBE = "session.reset_probe"

class FailureTypes(StrEnum):
    ASSERTION_FAILED = "ASSERTION_FAILED"
    FIXTURE_SETUP = "FIXTURE_SETUP"
    FIXTURE_CLEANUP = "FIXTURE_CLEANUP"
    INFRA_NETWORK = "INFRA_NETWORK"
    INFRA_TIMEOUT = "INFRA_TIMEOUT"
    INFRA_RESOURCE = "INFRA_RESOURCE"

class Features(StrEnum):
    JOIN = "join"
    UNION = "union"
    DDL_TABLE = "ddl_table"
    STRING_FUNCTION = "string_function"

class IsolationScopes(StrEnum):
    SESSION = "session"
    WORKER_SCHEMA = "worker_schema"
    CASE_SCHEMA = "case_schema"
    DATABASE = "database"
    CLUSTER = "cluster"

class Levels(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class ResourceAccessModes(StrEnum):
    SHARED_READ = "shared_read"
    EXCLUSIVE = "exclusive"

class StatusesAttempt(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"

class StatusesCaseAsset(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"

class StatusesCaseExecution(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    INFRA_RECOVERED = "INFRA_RECOVERED"

class StatusesStep(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
