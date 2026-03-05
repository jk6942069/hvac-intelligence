"""Workflow states match the acquisition pipeline (PE-specific)."""
from routers.dealdesk import WORKFLOW_STATUSES, WORKFLOW_MIGRATION_MAP


def test_new_workflow_states_present():
    expected = [
        "not_contacted", "contacted", "conversation_started",
        "meeting_scheduled", "under_review", "loi_considered", "passed",
    ]
    for state in expected:
        assert state in WORKFLOW_STATUSES, f"Missing workflow state: {state}"


def test_old_states_removed():
    old_states = ["responded", "interested", "not_interested", "follow_up",
                  "closed_lost", "closed_won"]
    for state in old_states:
        assert state not in WORKFLOW_STATUSES, f"Old state still present: {state}"


def test_migration_map_covers_all_old_states():
    old_states = ["not_contacted", "contacted", "responded", "interested",
                  "not_interested", "follow_up", "closed_lost", "closed_won"]
    for old in old_states:
        assert old in WORKFLOW_MIGRATION_MAP, f"No migration for: {old}"


def test_migration_map_targets_valid_new_states():
    for old, new in WORKFLOW_MIGRATION_MAP.items():
        assert new in WORKFLOW_STATUSES, f"Migration target {new!r} not valid"
