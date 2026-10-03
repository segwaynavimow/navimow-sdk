"""Tests for battery extraction semantics in mower_sdk.models.

The critical property under test: a payload that carries NO battery data
must parse as unknown (None), never as 0 — while an explicit zero reading
(a genuinely empty battery) must still parse as 0.
"""

from mower_sdk.models import (
    DeviceStateMessage,
    DeviceStatus,
    _extract_battery_value,
)


class TestExtractBatteryValue:
    def test_direct_battery_field(self):
        assert _extract_battery_value({"battery": 87}) == 87

    def test_direct_battery_field_zero_is_preserved(self):
        assert _extract_battery_value({"battery": 0}) == 0

    def test_capacity_remaining_percentage(self):
        payload = {
            "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 95}],
        }
        assert _extract_battery_value(payload) == 95

    def test_capacity_remaining_explicit_zero_is_preserved(self):
        # A genuinely flat battery, as reported by a real i105 on
        # 2026-10-02: explicit 0% plus descriptiveCapacityRemaining
        # CRITICALLY_LOW. Must stay 0, not become "unknown".
        payload = {
            "capacityRemaining": [{"unit": "PERCENTAGE", "rawValue": 0}],
            "descriptiveCapacityRemaining": "CRITICALLY_LOW",
        }
        assert _extract_battery_value(payload) == 0

    def test_capacity_remaining_skips_non_percentage_units(self):
        payload = {
            "capacityRemaining": [
                {"unit": "MILLIVOLT", "rawValue": 51000},
                {"unit": "PERCENTAGE", "rawValue": 64},
            ],
        }
        assert _extract_battery_value(payload) == 64

    def test_capacity_remaining_first_item_fallback(self):
        payload = {
            "capacityRemaining": [{"rawValue": 73}],
        }
        assert _extract_battery_value(payload) == 73

    def test_missing_battery_data_is_unknown_not_zero(self):
        # Regression guard: this used to return 0, which rendered as a
        # phantom "battery dropped to 0%" in downstream integrations
        # (see NavimowHA issue #84).
        assert _extract_battery_value({"id": "S4SFA2401K0104"}) is None
        assert _extract_battery_value({"capacityRemaining": []}) is None
        assert _extract_battery_value(
            {"capacityRemaining": [{"unit": "MILLIVOLT", "rawValue": 51000}]}
        ) is None
        assert _extract_battery_value({}) is None

    def test_unparseable_battery_values_are_unknown(self):
        assert _extract_battery_value({"battery": "n/a"}) is None


class TestDeviceStatusBattery:
    def test_status_without_battery_data_is_none(self):
        status = DeviceStatus.from_dict({"id": "dev1", "status": "idle"})
        assert status.battery is None

    def test_status_with_explicit_zero_battery(self):
        status = DeviceStatus.from_dict(
            {
                "id": "dev1",
                "status": "idle",
                "capacityRemaining": [
                    {"unit": "PERCENTAGE", "rawValue": 0}
                ],
            }
        )
        assert status.battery == 0

    def test_status_with_real_battery(self):
        status = DeviceStatus.from_dict(
            {"id": "dev1", "status": "idle", "battery": 86}
        )
        assert status.battery == 86


class TestDeviceStateMessageBattery:
    def test_state_message_without_battery_is_none(self):
        msg = DeviceStateMessage.from_dict(
            {"device_id": "dev1", "state": "isIdle"}
        )
        assert msg.battery is None

    def test_state_message_with_battery(self):
        msg = DeviceStateMessage.from_dict(
            {"device_id": "dev1", "state": "isIdle", "battery": 42}
        )
        assert msg.battery == 42

    def test_roundtrip_none_battery(self):
        msg = DeviceStateMessage.from_dict(
            {"device_id": "dev1", "state": "isIdle"}
        )
        assert msg.to_dict()["battery"] is None