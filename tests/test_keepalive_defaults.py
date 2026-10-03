"""Tests for the keepalive default.

The 2400s default let an intermediate network element reap the MQTT
connection after ~10 idle minutes without a FIN, so the client stayed
"connected" while receiving nothing (NavimowHA #70/#63 family). The
default is now 60s; explicit values are still honoured.
"""

import asyncio
import inspect

import pytest

from mower_sdk.mqtt import MowerMQTT, NavimowMQTT
from mower_sdk.sdk import NavimowSDK


@pytest.fixture
def loop():
    l = asyncio.new_event_loop()
    yield l
    l.close()


def default_of(fn, name):
    sig = inspect.signature(fn)
    return sig.parameters[name].default


class TestKeepaliveDefault:
    def test_navimow_mqtt_default_is_60(self):
        assert default_of(NavimowMQTT.__init__, "keepalive_seconds") == 60

    def test_legacy_mqtt_default_is_60(self):
        assert default_of(MowerMQTT.__init__, "keepalive_seconds") == 60

    def test_sdk_default_is_60(self):
        assert default_of(NavimowSDK.__init__, "keepalive_seconds") == 60

    def test_explicit_keepalive_is_honoured(self, loop):
        mqtt = NavimowMQTT(
            broker="mqtt-fra.navimow.com",
            port=443,
            username="u",
            password="p",
            records=[],
            ws_path="/mqtt",
            loop=loop,
            keepalive_seconds=120,
        )
        assert mqtt.keepalive_seconds == 120

    def test_floor_of_30s_still_applies(self, loop):
        mqtt = NavimowMQTT(
            broker="mqtt-fra.navimow.com",
            port=443,
            username="u",
            password="p",
            records=[],
            loop=loop,
            keepalive_seconds=5,
        )
        assert mqtt.keepalive_seconds == 30
