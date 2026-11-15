"""Optional local pacing preserves budgeted provider routing and independent workspaces."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from analogforge.adapters.openai.client import RateLimitCooldown, ResponsesClient
from tests.unit.platform.test_groq_fallback import configured


def test_separate_invocations_share_spacing_without_conversation_or_credentials():
    now = [100.0]
    state = RateLimitCooldown(lambda: now[0])
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    first, seen_a = configured(200, cooldown=state)
    second, seen_b = configured(200, cooldown=state)
    for client in [first, second]:
        client.min_request_interval_seconds, client.sleep = 7, sleep
    first.create(input="mission A")
    second.create(input="mission B")
    first.create(input="mission A continuation")
    assert waits == [7, 7]
    assert len(seen_a) == 2 and len(seen_b) == 1
    assert "mission A" not in str(seen_b)
    assert state.until == 0 and state.next_request_at == 121


def test_concurrent_reservations_are_serialized_without_holding_sleep_lock():
    state = RateLimitCooldown(lambda: 100)
    waits = []

    def sleep(seconds):
        assert state.lock.acquire(blocking=False)
        state.lock.release()
        waits.append(seconds)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: state.wait_for_slot(7, sleep), range(4)))
    assert sorted(waits) == [7, 14, 21]
    assert state.next_request_at == 128


def test_default_zero_pacing_has_no_wait_and_leaves_legacy_behavior():
    client, seen = configured(200)
    client.sleep = lambda _: pytest.fail("default pacing must not sleep")
    client.create(input="legacy")
    client.create(input="legacy continuation")
    assert len(seen) == 2 and client.cooldown.next_request_at == 0


def test_fallback_routing_does_not_consume_primary_slots_or_skip_request_charges():
    client, seen = configured()
    state = client.cooldown
    client.min_request_interval_seconds = 7
    client.sleep = lambda _: pytest.fail("only the first primary request is sent")
    charges = []
    client.create_budgeted(lambda: charges.append(True), input="first")
    first_slot = state.next_request_at
    client.create_budgeted(lambda: charges.append(True), input="fallback continuation")
    assert [row[0] for row in seen] == ["openai", "groq", "groq"]
    assert charges == [True] and state.next_request_at == first_slot


@pytest.mark.parametrize("value", [-1, 61, float("nan"), float("inf")])
def test_invalid_pacing_rejected_before_any_request(value):
    with pytest.raises(ValueError, match="request pacing"):
        ResponsesClient("fake-key", "model", min_request_interval_seconds=value)  # noqa: S106
