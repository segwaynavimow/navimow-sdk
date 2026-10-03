"""Tests for the location channel wiring and MQTT topic layout.

The broker's real downlink layout is
/downlink/vehicle/<device_id>/realtimeDate/<channel> with four channels:
state, event, attributes, and location. The location channel feeds the
live position that NavimowHA issues #55 / #91 report as never
populating.
"""

import asyncio
import json

from mower_sdk.models import DeviceLocationMessage
from mower_sdk.mqtt import NavimowMQTT
from mower_sdk.sdk import NavimowSDK


class FakeRecords:
    """Minimal stand-in for mower_sdk.models.Device list entries."""

    def __init__(self, ids):
        self.ids = list(ids)

    def __iter__(self):
        return iter(self.ids)


def make_sdk_with_spy():
    """Build a NavimowSDK-ish object exposing _on_mqtt_message + caches."""
    sdk = NavimowSDK.__new__(NavimowSDK)
    sdk._state_callbacks = []
    sdk._event_callbacks = []
    sdk._attributes_callbacks = []
    sdk._location_callbacks = []
    sdk._state_cache = {}
    sdk._event_cache = {}
    sdk._attributes_cache = {}
    sdk._location_cache = {}
    seen = []
    sdk.on_location(seen.append)
    return sdk, seen


def deliver(sdk, channel, payload, device_id="S4SFA2401K0104"):
    topic = f"/downlink/vehicle/{device_id}/realtimeDate/{channel}"
    body = json.dumps(payload).encode("utf-8")
    asyncio.run(sdk._on_mqtt_message(topic, body, device_id))


class TestLocationDispatch:
    def test_location_message_parses_string_coordinates(self):
        # Field shapes captured from the live broker (documented by the
        # ioBroker adapter for the same cloud): measurements arrive as
        # JSON strings.
        sdk, seen = make_sdk_with_spy()
        deliver(
            sdk,
            "location",
            {
                "postureX": "0.329",
                "postureY": "1.234",
                "postureTheta": "2.1",
                "time": 1759512345,
                "vehicleState": 7,
                "subtotalArea": "734.08",
                "mowingWeekArea": "",
            },
        )
        assert len(seen) == 1
        msg = seen[0]
        assert msg.x == 0.329
        assert msg.y == 1.234
        assert msg.theta == 2.1
        assert msg.time == 1759512345
        assert msg.subtotal_area == 734.08
        assert msg.mowing_week_area is None  # empty string stays unknown
        assert msg.is_complete
        assert sdk.get_cached_location("S4SFA2401K0104") is msg

    def test_missing_coordinates_are_incomplete(self):
        msg = DeviceLocationMessage.from_dict({"device_id": "d1"})
        assert msg.x is None and msg.y is None
        assert not msg.is_complete

    def test_numeric_json_values_also_parse(self):
        msg = DeviceLocationMessage.from_dict(
            {"postureX": 0.5, "postureY": 2.5}
        )
        assert (msg.x, msg.y) == (0.5, 2.5)

    def test_other_channels_still_dispatch(self):
        sdk, seen = make_sdk_with_spy()
        deliver(sdk, "state", {"state": "isIdle", "battery": 86})
        cached = sdk.get_cached_state("S4SFA2401K0104")
        assert cached is not None
        assert seen == []


class TestSubscriptionTopics:
    def test_subscribe_all_covers_all_four_channels(self):
        mqtt = NavimowMQTT.__new__(NavimowMQTT)
        subscribed = []
        mqtt.client = type("C", (), {"subscribe": staticmethod(subscribed.append)})()
        mqtt.records = [type("D", (), {"id": "S4SFA2401K0104"})()]
        mqtt.subscribe_all("", "")
        expected = {
            "/downlink/vehicle/S4SFA2401K0104/realtimeDate/state",
            "/downlink/vehicle/S4SFA2401K0104/realtimeDate/event",
            "/downlink/vehicle/S4SFA2401K0104/realtimeDate/attributes",
            "/downlink/vehicle/S4SFA2401K0104/realtimeDate/location",
        }
        assert set(subscribed) == expected
        assert len(subscribed) == 4

    def test_subscribe_all_wildcard_covers_all_four_channels(self):
        mqtt = NavimowMQTT.__new__(NavimowMQTT)
        subscribed = []
        mqtt.client = type("C", (), {"subscribe": staticmethod(subscribed.append)})()
        mqtt.records = []
        mqtt.subscribe_all("", "")
        assert subscribed == [
            "/downlink/vehicle/+/realtimeDate/state",
            "/downlink/vehicle/+/realtimeDate/event",
            "/downlink/vehicle/+/realtimeDate/attributes",
            "/downlink/vehicle/+/realtimeDate/location",
        ]

    def test_unsubscribe_all_covers_all_four_channels(self):
        mqtt = NavimowMQTT.__new__(NavimowMQTT)
        unsubscribed = []
        mqtt.client = type("C", (), {"unsubscribe": staticmethod(unsubscribed.append)})()
        mqtt.records = [type("D", (), {"id": "S4SFA2401K0104"})()]
        mqtt.unsubscribe_all("", "")
        assert len(unsubscribed) == 4
        assert "/downlink/vehicle/S4SFA2401K0104/realtimeDate/location" in unsubscribed


class TestLegacyTopics:
    def test_legacy_status_topic_is_real_cloud_layout(self):
        from mower_sdk.mqtt import MowerMQTT

        legacy = MowerMQTT.__new__(MowerMQTT)
        assert legacy._get_status_topic("dev1") == (
            "/downlink/vehicle/dev1/realtimeDate/state"
        )
        assert legacy._get_event_topic("dev1") == (
            "/downlink/vehicle/dev1/realtimeDate/event"
        )