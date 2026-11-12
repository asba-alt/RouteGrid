"""Order lifecycle rules from requirements.md FR-6 and FR-4."""
from app.services.order_service import ALLOWED_TRANSITIONS, PENDING_ALLOCATION

LIFECYCLE_STATES = {
    "PENDING_ALLOCATION",
    "ALLOCATED",
    "PICKING",
    "READY_FOR_DISPATCH",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "PARTIALLY_SHIPPED",
    "CANCELLED",
    "FAILED",
}

TERMINAL_STATES = {"DELIVERED", "CANCELLED", "FAILED"}


def test_transition_map_covers_the_documented_lifecycle():
    assert set(ALLOWED_TRANSITIONS) == LIFECYCLE_STATES


def test_new_orders_start_pending_allocation():
    assert PENDING_ALLOCATION == "PENDING_ALLOCATION"
    assert "ALLOCATED" in ALLOWED_TRANSITIONS[PENDING_ALLOCATION]


def test_terminal_states_have_no_outgoing_transitions():
    for state in TERMINAL_STATES:
        assert ALLOWED_TRANSITIONS[state] == set()


def test_cancellation_rejected_at_or_after_out_for_delivery():
    """FR-4: a group cannot be cancelled once it is out for delivery."""
    assert "CANCELLED" not in ALLOWED_TRANSITIONS["OUT_FOR_DELIVERY"]
    assert "CANCELLED" in ALLOWED_TRANSITIONS["READY_FOR_DISPATCH"]


def test_partially_shipped_can_still_complete():
    assert ALLOWED_TRANSITIONS["PARTIALLY_SHIPPED"] == {"DELIVERED", "FAILED"}


def test_no_target_state_is_undefined():
    for targets in ALLOWED_TRANSITIONS.values():
        assert targets <= LIFECYCLE_STATES
