from xgtest.core.admission import evaluate_admission
from xgtest.core.models import ResourceRequest
from xgtest.generated.registry_enums import IsolationScope, ResourceAccessMode


def _request(resource_id: str, mode: ResourceAccessMode, parent: str | None = None) -> ResourceRequest:
    return ResourceRequest(
        resource_type="schema",
        resource_id=resource_id,
        scope=IsolationScope.CASE_SCHEMA,
        access_mode=mode,
        impact_scope="schema",
        parent_identity=parent,
    )


def test_resource_conflict_matrix_is_symmetric_for_shared_resources() -> None:
    held_read = _request("schema-a", ResourceAccessMode.SHARED_READ)
    requested_read = _request("schema-a", ResourceAccessMode.SHARED_READ)
    requested_write = _request("schema-a", ResourceAccessMode.SHARED_WRITE)
    assert evaluate_admission((held_read,), (requested_read,)).allowed
    assert not evaluate_admission((held_read,), (requested_write,)).allowed
    assert not evaluate_admission((requested_write,), (held_read,)).allowed


def test_resource_conflict_matrix_expands_direct_parent_and_same_owner() -> None:
    held_database = _request("database-a", ResourceAccessMode.EXCLUSIVE)
    requested_schema = _request("schema-a", ResourceAccessMode.SHARED_READ, parent="database-a")
    assert not evaluate_admission((held_database,), (requested_schema,)).allowed
    assert evaluate_admission((held_database,), (requested_schema,), same_owner=True).allowed


def test_unrelated_resources_are_admitted() -> None:
    held = _request("schema-a", ResourceAccessMode.EXCLUSIVE)
    requested = _request("schema-b", ResourceAccessMode.EXCLUSIVE)
    decision = evaluate_admission((held,), (requested,))
    assert decision.allowed
    assert decision.conflicts == ()


def test_v01_does_not_expand_grandparents_or_enforce_quantity() -> None:
    grandparent = _request("cluster-a", ResourceAccessMode.EXCLUSIVE)
    grandchild = _request("schema-a", ResourceAccessMode.SHARED_READ, parent="database-a")
    assert evaluate_admission((grandparent,), (grandchild,)).allowed
    first = _request("schema-a", ResourceAccessMode.SHARED_READ).model_copy(update={"quantity": 100})
    second = _request("schema-a", ResourceAccessMode.SHARED_READ).model_copy(update={"quantity": 100})
    assert evaluate_admission((first,), (second,)).allowed
