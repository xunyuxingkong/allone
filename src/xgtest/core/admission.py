"""Admission Conflict Rules v0.1: pure pairwise conflict evaluation only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from xgtest.core.models import ResourceRequest
from xgtest.generated.registry_enums import ResourceAccessMode


ADMISSION_RULES_VERSION = "0.1"


@dataclass(frozen=True)
class AdmissionConflict:
    resource_id: str
    held_mode: ResourceAccessMode
    requested_mode: ResourceAccessMode
    reason: str


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    conflicts: tuple[AdmissionConflict, ...] = ()


def _overlap(left: ResourceRequest, right: ResourceRequest) -> bool:
    """Return whether two requests name the same resource or a direct parent."""
    return (
        left.resource_id == right.resource_id
        or left.resource_id == right.parent_identity
        or right.resource_id == left.parent_identity
    )


def _mode_conflicts(held: ResourceAccessMode, requested: ResourceAccessMode) -> bool:
    # READ/READ is the only shared combination. WRITE and EXCLUSIVE are
    # mutually exclusive across different owners.
    return not (held == ResourceAccessMode.SHARED_READ and requested == ResourceAccessMode.SHARED_READ)


def evaluate_admission(
    held: Iterable[ResourceRequest],
    requested: Iterable[ResourceRequest],
    *,
    same_owner: bool = False,
) -> AdmissionDecision:
    """Evaluate a batch with the v0.1 access-mode matrix.

    ``same_owner`` models multiple sessions within one Attempt. They are
    merged by the caller and must not block one another at Admission level.
    This pure function does not grant resources, track capacity, traverse
    multi-level ancestors, or provide a persistent atomic lease.
    """
    if same_owner:
        return AdmissionDecision(allowed=True)
    held_requests = tuple(held)
    requested_requests = tuple(requested)
    conflicts: list[AdmissionConflict] = []
    for existing in held_requests:
        for candidate in requested_requests:
            if _overlap(existing, candidate) and _mode_conflicts(existing.access_mode, candidate.access_mode):
                conflicts.append(AdmissionConflict(
                    resource_id=candidate.resource_id,
                    held_mode=existing.access_mode,
                    requested_mode=candidate.access_mode,
                    reason="ACCESS_MODE_CONFLICT",
                ))
    return AdmissionDecision(allowed=not conflicts, conflicts=tuple(conflicts))
