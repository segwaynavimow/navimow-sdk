"""Cloud MQTT parsing and dispatch."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mower_sdk.event import DataEvent
from mower_sdk.models import (
    DeviceAttributesMessage,
    DeviceEventMessage,
    DeviceStateMessage,
)
from mower_sdk.mqtt import NavimowMQTT

_LOGGER = logging.getLogger(__name__)


class NavimowCloud:
    """Per-account MQTT cloud."""

    def __init__(self, mqtt_client: NavimowMQTT, cloud_client: Any) -> None:
        self.cloud_client = cloud_client
        self.loop = asyncio.get_event_loop()
        self._mqtt_client = mqtt_client
        self._mqtt_client.on_message = self._on_mqtt_message
        self._mqtt_client.on_connected = self.on_connected
        self._mqtt_client.on_disconnected = self.on_disconnected
        self._mqtt_client.on_ready = self.on_ready

        self.mqtt_event_message_event = DataEvent()
        self.mqtt_attributes_event = DataEvent()
        self.mqtt_state_event = DataEvent()
        self.on_ready_event = DataEvent()
        self.on_connected_event = DataEvent()
        self.on_disconnected_event = DataEvent()

    def connect_async(self) -> None:
        self._mqtt_client.connect_async()

    def disconnect(self) -> None:
        self._mqtt_client.disconnect()

    async def on_ready(self) -> None:
        await self.on_ready_event.data_event(None)

    async def on_connected(self) -> None:
        await self.on_connected_event.data_event(None)

    async def on_disconnected(self) -> None:
        await self.on_disconnected_event.data_event(None)

    async def _on_mqtt_message(self, topic: str, payload: bytes, device_id: str) -> None:
        try:
            json_str = payload.decode("utf-8")
            payload_dict = json.loads(json_str)
        except (UnicodeDecodeError, json.JSONDecodeError):
            _LOGGER.debug("MQTT payload not json: topic=%s", topic)
            return

        if isinstance(payload_dict, dict):
            payload_dict.setdefault("device_id", device_id)
        await self._parse_mqtt_response(topic, payload_dict)

    async def _parse_mqtt_response(self, topic: str, payload: dict[str, Any]) -> None:
        """Parse MQTT response by topic channel and emit data events."""
        parts = topic.split("/")
        if len(parts) != 3 or parts[0] != "navimow":
            return
        channel = parts[2]
        if channel == "state":
            state = DeviceStateMessage.from_dict(payload)
            await self.mqtt_state_event.data_event(state)
            return
        if channel == "event":
            event = DeviceEventMessage.from_dict(payload)
            await self.mqtt_event_message_event.data_event(event)
            return
        if channel == "attributes":
            attrs = DeviceAttributesMessage.from_dict(payload)
            await self.mqtt_attributes_event.data_event(attrs)
