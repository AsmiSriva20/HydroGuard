from types import SimpleNamespace

import pytest

from app.models.payloads import ConditionStatus, SensorPayload
from app.services.alert_service import cooldown_allows
from app.services.analytics_service import usage_segments
from app.services.state_machine import derive_condition_status
from simulator.__main__ import _parse_args


def sample(timestamp=0, rate=6, human=0, flowing=1):
    return SimpleNamespace(
        timestamp=timestamp, flow_rate_lpm=rate, human_present=human, water_flow=flowing
    )


def test_usage_and_waste_integrate_previous_rate():
    assert usage_segments(sample(), 30, 60) == [{"day": 0, "used_litres": 3, "wasted_litres": 3}]
    assert usage_segments(sample(human=1), 30, 60)[0]["wasted_litres"] == 0


def test_no_invented_volume_in_offline_gaps_or_duplicates():
    assert usage_segments(sample(), 61, 60) == []
    assert usage_segments(sample(), 0, 60) == []
    assert usage_segments(sample(), -1, 60) == []
    assert usage_segments(None, 10, 60) == []
    assert usage_segments(sample(flowing=0), 30, 60)[0]["used_litres"] == 0


def test_midnight_splits_usage_between_days():
    rows = usage_segments(sample(timestamp=86390), 86410, 60)
    assert rows == [
        {"day": 0, "used_litres": 1, "wasted_litres": 1},
        {"day": 86400, "used_litres": 1, "wasted_litres": 1},
    ]


def test_cooldown_suppresses_duplicates_and_allows_escalation():
    assert not cooldown_allows("LEAK", "LEAK", {"LEAK": 100}, 399, 300)
    assert cooldown_allows("LEAK", "LEAK", {"LEAK": 100}, 400, 300)
    assert cooldown_allows("CRITICAL", "WARNING", {"CRITICAL": 100}, 101, 300)
    assert not cooldown_allows("WARNING", "CRITICAL", {"WARNING": 100}, 101, 300)


def test_critical_requires_substantial_flow():
    payload = SensorPayload(
        device_id="lab", timestamp=1, water_flowing=True, leak_detected=True, flow_rate_lpm=0.1
    )
    assert derive_condition_status(payload, 300, 0.3) == ConditionStatus.LEAK
    payload.flow_rate_lpm = 0.4
    assert derive_condition_status(payload, 300, 0.3) == ConditionStatus.CRITICAL


@pytest.mark.parametrize(
    "scenario",
    ["normal", "normal_usage", "unattended_flow", "leak", "critical_leak", "device_offline"],
)
def test_simulator_named_scenarios(scenario):
    args = _parse_args([scenario, "--device", "washroom_01", "--duration", "2"])
    assert args.device_id == "washroom_01"


def test_simulator_rejects_zero_tick():
    with pytest.raises(SystemExit):
        _parse_args(["normal", "--tick", "0"])
