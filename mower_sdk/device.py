"""Device classes for cloud MQTT handling."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from mower_sdk.cloud import NavimowCloud
from mower_sdk.models import (
    Device,
    DeviceAttributesMessage,
    DeviceEventMessage,
    DeviceStateMessage,
)
from mower_sdk.state_manager import StateManager


class NavimowCloudDevice:
    """Device with cloud MQTT connectivity."""

    def __init__(self, cloud: NavimowCloud, device: Device, state_manager: StateManager) -> None:
        self.cloud = cloud
        self.device = device
        self.state_manager = state_manager
        self.device_id = device.id

        self.cloud.mqtt_event_message_event.add_subscribers(
            self._parse_message_for_device
        )
        self.cloud.mqtt_attributes_event.add_subscribers(
            self._parse_message_attributes_for_device
        )
        self.cloud.mqtt_state_event.add_subscribers(self._parse_message_state_for_device)

    def __del__(self) -> None:
        self.cloud.mqtt_event_message_event.remove_subscribers(
            self._parse_message_for_device
        )
        self.cloud.mqtt_attributes_event.remove_subscribers(
            self._parse_message_attributes_for_device
        )
        self.cloud.mqtt_state_event.remove_subscribers(
            self._parse_message_state_for_device
        )

    def set_notification_callback(
        self, func: Callable[[tuple[str, object | None]], Awaitable[None]]
    ) -> None:
        self.state_manager.cloud_on_notification_callback.add_subscribers(func)

    async def _parse_message_attributes_for_device(
        self, event: DeviceAttributesMessage
    ) -> None:
        if event.device_id != self.device_id:
            return
        await self.state_manager.attributes(event)

    async def _parse_message_state_for_device(self, state: DeviceStateMessage) -> None:
        if state.device_id != self.device_id:
            return
        await self.state_manager.state(state)

    async def _parse_message_for_device(self, event: DeviceEventMessage) -> None:
        if event.device_id != self.device_id:
            return
        await self.state_manager.device_event(event)
