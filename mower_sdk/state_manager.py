"""State manager for device updates."""

from __future__ import annotations

from mower_sdk.event import DataEvent
from mower_sdk.models import (
    Device,
    DeviceAttributesMessage,
    DeviceEventMessage,
    DeviceStateMessage,
)


class StateManager:
    """Manage device state from MQTT messages."""

    def __init__(self, device: Device) -> None:
        self._device = device
        self.attributes_callback = DataEvent()
        self.state_callback = DataEvent()
        self.event_callback = DataEvent()
        self.cloud_on_notification_callback = DataEvent()

        self._last_attributes: DeviceAttributesMessage | None = None
        self._last_state: DeviceStateMessage | None = None
        self._last_event: DeviceEventMessage | None = None

    @property
    def device(self) -> Device:
        return self._device

    @property
    def last_attributes(self) -> DeviceAttributesMessage | None:
        return self._last_attributes

    @property
    def last_state(self) -> DeviceStateMessage | None:
        return self._last_state

    @property
    def last_event(self) -> DeviceEventMessage | None:
        return self._last_event

    def get_device_state(self) -> DeviceStateMessage | None:
        return self._last_state

    async def attributes(self, event: DeviceAttributesMessage) -> None:
        self._last_attributes = event
        await self.attributes_callback.data_event(event)

    async def state(self, state: DeviceStateMessage) -> None:
        self._last_state = state
        await self.state_callback.data_event(state)

    async def device_event(self, event: DeviceEventMessage) -> None:
        self._last_event = event
        await self.event_callback.data_event(event)

    async def notification(self, data: Any) -> None:
        await self.cloud_on_notification_callback.data_event(data)
