"""Navimow device manager and cloud initialization."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from mower_sdk.cloud import NavimowCloud
from mower_sdk.device import NavimowCloudDevice
from mower_sdk.models import Device
from mower_sdk.mqtt import NavimowMQTT
from mower_sdk.state_manager import StateManager


class NavimowDeviceManager:
    """Manage Navimow cloud devices."""

    def __init__(self) -> None:
        self.devices: dict[str, NavimowCloudDevice] = {}

    def add_device(self, device: NavimowCloudDevice) -> None:
        self.devices[device.device.id] = device

    def get_device_by_name(self, name: str) -> NavimowCloudDevice | None:
        for device in self.devices.values():
            if device.device.name == name:
                return device
        return None

    def get_device_by_id(self, device_id: str) -> NavimowCloudDevice | None:
        return self.devices.get(device_id)


class Navimow:
    """Navimow account manager."""

    def __init__(self, client: "MowerClient") -> None:
        self.client = client
        self.device_manager = NavimowDeviceManager()
        self.cloud: NavimowCloud | None = None

    async def initiate_cloud_connection(
        self,
        devices: list[Device],
        executor: Callable[[Callable[[], NavimowMQTT]], "asyncio.Future[NavimowMQTT]"]
        | None = None,
    ) -> NavimowCloud:
        if self.cloud is not None:
            return self.cloud

        await self.client.async_refresh_mqtt_info()
        loop = asyncio.get_running_loop()
        def _build_mqtt() -> NavimowMQTT:
            return NavimowMQTT(
                broker=self.client.mqtt_broker,
                port=self.client.mqtt_port,
                username=self.client.mqtt_username,
                password=self.client.mqtt_password,
                records=devices,
                ws_path=self.client.mqtt_ws_path,
                auth_headers={"Authorization": f"Bearer {self.client.get_token()}"},
                loop=loop,
            )

        if executor is not None:
            mqtt = await executor(_build_mqtt)
        else:
            mqtt = _build_mqtt()
        cloud = NavimowCloud(mqtt, cloud_client=self.client)
        cloud.connect_async()
        self.cloud = cloud
        return cloud

    def add_devices(self, devices: list[Device]) -> list[NavimowCloudDevice]:
        if self.cloud is None:
            raise RuntimeError("Cloud connection not initialized")
        results: list[NavimowCloudDevice] = []
        for device in devices:
            state_manager = StateManager(device)
            cloud_device = NavimowCloudDevice(self.cloud, device, state_manager)
            self.device_manager.add_device(cloud_device)
            results.append(cloud_device)
        return results

    def get_device_by_name(self, name: str) -> NavimowCloudDevice | None:
        return self.device_manager.get_device_by_name(name)

    def get_device_by_id(self, device_id: str) -> NavimowCloudDevice | None:
        return self.device_manager.get_device_by_id(device_id)
