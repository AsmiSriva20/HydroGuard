import pytest
from fastapi import HTTPException

from app.api.demo import (
    DemoScenario,
    _demo_action_times,
    _enforce_public_demo_rate_limit,
    _require_public_demo,
    build_demo_payload,
)
from app.core.config import Settings
from app.models.payloads import ConditionStatus, derive_condition_status


@pytest.mark.parametrize(
    "scenario, expected_status",
    [
        (DemoScenario.NORMAL, ConditionStatus.NORMAL),
        (DemoScenario.NORMAL_FLOW, ConditionStatus.NORMAL_FLOW),
        (DemoScenario.WARNING, ConditionStatus.WARNING),
        (DemoScenario.ALERT, ConditionStatus.ALERT),
        (DemoScenario.LEAK, ConditionStatus.LEAK),
        (DemoScenario.CRITICAL, ConditionStatus.CRITICAL),
    ],
)
def test_demo_scenarios_map_to_expected_backend_states(
    scenario: DemoScenario,
    expected_status: ConditionStatus,
) -> None:
    payload = build_demo_payload(
        scenario=scenario,
        device_id="device01",
        timestamp=1_700_000_000,
        threshold_sec=300,
    )

    assert derive_condition_status(payload, 300) == expected_status


def test_public_demo_can_be_disabled() -> None:
    settings = Settings(
        demo_public_actions_enabled=False,
        demo_device_id="device01",
    )

    with pytest.raises(HTTPException) as exc_info:
        _require_public_demo(settings, "device01")

    assert exc_info.value.status_code == 404


def test_public_demo_enabled_does_not_require_admin_key() -> None:
    settings = Settings(
        demo_public_actions_enabled=True,
        demo_device_id="device01",
        admin_api_key="server-only-secret",
        app_env="production",
    )

    _require_public_demo(settings, "device01")


def test_public_demo_rejects_other_device() -> None:
    settings = Settings(
        demo_public_actions_enabled=True,
        demo_device_id="device01",
    )

    with pytest.raises(HTTPException) as exc_info:
        _require_public_demo(settings, "device02")

    assert exc_info.value.status_code == 404


@pytest.fixture(autouse=True)
def clear_demo_rate_limit_state():
    _demo_action_times.clear()
    yield
    _demo_action_times.clear()


def test_public_demo_rate_limit_blocks_excess_actions() -> None:
    settings = Settings(demo_rate_limit_per_minute=2)

    _enforce_public_demo_rate_limit(settings, now=100.0)
    _enforce_public_demo_rate_limit(settings, now=101.0)

    with pytest.raises(HTTPException) as exc_info:
        _enforce_public_demo_rate_limit(settings, now=102.0)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "60"


def test_public_demo_rate_limit_allows_actions_after_window() -> None:
    settings = Settings(demo_rate_limit_per_minute=1)

    _enforce_public_demo_rate_limit(settings, now=100.0)
    _enforce_public_demo_rate_limit(settings, now=161.0)
