"""Navimow SDK facade for MQTT-based integration."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from typing import Any

from mower_sdk.models import (
    DeviceAttributesMessage,
    DeviceCommandMessage,
    DeviceEventMessage,
    DeviceStateMessage,
)
from mower_sdk.mqtt import NavimowMQTT

_LOGGER = logging.getLogger(__name__)


class NavimowSDK:
    """SDK facade.

    Notes:
        - on_state/on_event/on_attributes callbacks are synchronous.
        - callbacks are invoked from the MQTT thread/event loop context.
          Home Assistant must switch to hass loop via call_soon_threadsafe or
          run_coroutine_threadsafe.
    """

    def __init__(
        self,
        broker: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        ws_path: str | None = None,
        auth_headers: dict[str, str] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        records: list[Any] | None = None,
        keepalive_seconds: int = 2400,
        reconnect_min_delay: int = 1,
        reconnect_max_delay: int = 60,
    ) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._mqtt = NavimowMQTT(
            broker=broker,
            port=port,
            username=username,
            password=password,
            records=records or [],
            ws_path=ws_path,
            auth_headers=auth_headers,
            loop=self._loop,
            keepalive_seconds=keepalive_seconds,
            reconnect_min_delay=reconnect_min_delay,
            reconnect_max_delay=reconnect_max_delay,
        )
        self._mqtt.on_message = self._on_mqtt_message

        self._state_callbacks: list[Callable[[DeviceStateMessage], None]] = []
        self._event_callbacks: list[Callable[[DeviceEventMessage], None]] = []
        self._attributes_callbacks: list[Callable[[DeviceAttributesMessage], None]] = []

        self._state_cache: dict[str, DeviceStateMessage] = {}
        self._attributes_cache: dict[str, DeviceAttributesMessage] = {}

    def connect(self) -> None:
        """Connect to MQTT broker and start consuming."""
        self._mqtt.connect_async()

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._mqtt.disconnect()

    def update_mqtt_credentials(
        self,
        username: str | None = None,
        password: str | None = None,
        auth_headers: dict[str, str] | None = None,
    ) -> None:
        """更新 MQTT 凭据。若与当前值不同，将重建 paho client 并重连。

        用于 OAuth token 刷新后同步更新 MQTT WebSocket 认证头，
        以及更新服务端下发的 MQTT username/password。
        """
        self._mqtt.update_credentials(
            username=username,
            password=password,
            auth_headers=auth_headers,
        )

    def on_state(self, callback: Callable[[DeviceStateMessage], None]) -> None:
        self._state_callbacks.append(callback)

    def on_event(self, callback: Callable[[DeviceEventMessage], None]) -> None:
        self._event_callbacks.append(callback)

    def on_attributes(self, callback: Callable[[DeviceAttributesMessage], None]) -> None:
        self._attributes_callbacks.append(callback)

    def get_cached_state(self, device_id: str) -> DeviceStateMessage | None:
        return self._state_cache.get(device_id)

    def get_cached_attributes(self, device_id: str) -> DeviceAttributesMessage | None:
        return self._attributes_cache.get(device_id)

    async def _on_mqtt_message(
        self, topic: str, payload: bytes, device_id: str
    ) -> None:
        try:
            payload_dict = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(payload_dict, dict):
            return

        payload_dict.setdefault("device_id", device_id)
        parts = topic.split("/")
        if parts and parts[0] == "":
            parts = parts[1:]
        if len(parts) != 5:
            return
        if parts[0] != "downlink" or parts[1] != "vehicle":
            return
        if parts[3] != "realtimeDate":
            return
        channel = parts[4]

        if channel == "state":
            msg = DeviceStateMessage.from_dict(payload_dict)
            self._state_cache[msg.device_id] = msg
            for cb in list(self._state_callbacks):
                cb(msg)
            return
        if channel == "event":
            msg = DeviceEventMessage.from_dict(payload_dict)
            for cb in list(self._event_callbacks):
                cb(msg)
            return
        if channel == "attributes":
            msg = DeviceAttributesMessage.from_dict(payload_dict)
            self._attributes_cache[msg.device_id] = msg
            for cb in list(self._attributes_callbacks):
                cb(msg)

    def _publish_command(self, message: DeviceCommandMessage) -> None:
        if not self._mqtt.is_connected:
            self._mqtt.connect_async()
            _LOGGER.error(
                "MQTT not connected, command not sent: %s for device %s",
                message.command,
                message.device_id,
            )
            raise RuntimeError("MQTT not connected")
        self._mqtt.publish_command(message.device_id, message.to_dict())
        _LOGGER.debug(
            "Published command %s for device %s",
            message.command,
            message.device_id,
        )

    @property
    def is_connected(self) -> bool:
        return self._mqtt.is_connected

    def start_mowing(self, device_id: str) -> None:
        self._publish_command(
            DeviceCommandMessage(
                id=f"cmd-{uuid.uuid4()}",
                device_id=device_id,
                command="start_mowing",
                params={},
            )
        )

    def pause(self, device_id: str) -> None:
        self._publish_command(
            DeviceCommandMessage(
                id=f"cmd-{uuid.uuid4()}",
                device_id=device_id,
                command="pause",
                params={},
            )
        )

    def return_to_base(self, device_id: str) -> None:
        self._publish_command(
            DeviceCommandMessage(
                id=f"cmd-{uuid.uuid4()}",
                device_id=device_id,
                command="return_to_base",
                params={},
            )
        )

    def set_blade_height(self, device_id: str, height: int) -> None:
        self._publish_command(
            DeviceCommandMessage(
                id=f"cmd-{uuid.uuid4()}",
                device_id=device_id,
                command="set_blade_height",
                params={"height": height},
            )
        )
