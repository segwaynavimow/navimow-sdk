"""Main client module.

主客户端模块。

Provides a unified client interface that aggregates all functionality.

提供聚合所有功能的统一客户端接口。
"""

import asyncio
from typing import Any, Callable, TYPE_CHECKING

from mower_sdk.api import MowerAPI
from mower_sdk.models import Device, DeviceStatus, MowerCommand
from mower_sdk.mqtt import MowerMQTT

if TYPE_CHECKING:
    import aiohttp


class MowerClient:
    """Main mower platform client.

    割草机平台主客户端。

    Aggregates REST API and MQTT functionality to provide a unified interface.

    聚合 REST API 和 MQTT 功能，提供统一的接口。

    Attributes:
        api: REST API client
        api: REST API 客户端
        mqtt: MQTT client
        mqtt: MQTT 客户端
    """

    def __init__(
        self,
        session: "aiohttp.ClientSession",
        token: str,
        api_base_url: str = "",
        mqtt_broker: str = "",
        mqtt_port: int = 1883,
        mqtt_username: str | None = None,
        mqtt_password: str | None = None,
    ):
        """Initialize the main client.

        初始化主客户端。

        Args:
            session: aiohttp session
            session: aiohttp 会话
            token: Access token
            token: 访问令牌
            api_base_url: REST API base URL
            api_base_url: REST API 基础 URL
            mqtt_broker: MQTT broker address
            mqtt_broker: MQTT broker 地址
            mqtt_port: MQTT broker port
            mqtt_port: MQTT broker 端口
            mqtt_username: MQTT username, optional
            mqtt_username: MQTT 用户名（可选）
            mqtt_password: MQTT password, optional
            mqtt_password: MQTT 密码（可选）
        """
        self.api = MowerAPI(session=session, token=token, base_url=api_base_url)
        self.mqtt = MowerMQTT(
            broker=mqtt_broker,
            port=mqtt_port,
            username=mqtt_username,
            password=mqtt_password,
        )
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.mqtt_ws_path: str | None = None
        self._token = token

    def update_token(self, token: str) -> None:
        """Update the access token.

        更新访问令牌。
        """
        self._token = token
        self.api.set_token(token)

    async def async_refresh_mqtt_info(self) -> dict[str, Any]:
        """Refresh MQTT connection information asynchronously.

        异步刷新 MQTT 连接信息。
        """
        info = await self.api.async_get_mqtt_user_info()
        mqtt_host = info.get("mqttHost", "")
        mqtt_url = info.get("mqttUrl", "")
        username = info.get("userName")
        password = info.get("pwdInfo")
        self.mqtt_broker = mqtt_host
        self.mqtt_port = 443
        self.mqtt_username = username
        self.mqtt_password = password
        self.mqtt_ws_path = mqtt_url
        auth_headers = {"Authorization": f"Bearer {self._token}"}
        self.mqtt.configure_wss(
            mqtt_host=mqtt_host,
            mqtt_url=mqtt_url,
            username=username,
            password=password,
            auth_headers=auth_headers,
            port=self.mqtt_port,
        )
        return info

    def refresh_mqtt_info(self) -> dict[str, Any]:
        """Refresh MQTT connection information synchronously.

        同步刷新 MQTT 连接信息。
        """
        return asyncio.run(self.async_refresh_mqtt_info())

    async def async_discover_devices(self) -> list[Device]:
        """异步发现设备。

        Returns:
            设备列表

        Raises:
            MowerAPIError: 如果请求失败
        """
        return await self.api.async_get_devices()

    def discover_devices(self) -> list[Device]:
        """同步发现设备。

        Returns:
            设备列表

        Raises:
            MowerAPIError: 如果请求失败
        """
        return self.api.get_devices()

    async def async_subscribe_device_updates(
        self,
        device_id: str,
        callback: Callable[[DeviceStatus], None] | None = None,
    ) -> None:
        """异步订阅设备状态更新。

        Args:
            device_id: 设备 ID
            callback: 状态更新回调函数

        Raises:
            MowerMQTTError: 如果订阅失败
        """
        await self.async_refresh_mqtt_info()
        await self.mqtt.async_connect()
        await self.mqtt.async_subscribe_device(
            device_id=device_id,
            on_status_update=callback,
        )

    def subscribe_device_updates(
        self,
        device_id: str,
        callback: Callable[[DeviceStatus], None] | None = None,
    ) -> None:
        """同步订阅设备状态更新。

        Args:
            device_id: 设备 ID
            callback: 状态更新回调函数

        Raises:
            MowerMQTTError: 如果订阅失败
        """
        self.refresh_mqtt_info()
        self.mqtt.connect()
        self.mqtt.subscribe_device(
            device_id=device_id,
            on_status_update=callback,
        )

    async def async_start_mowing(self, device_id: str) -> dict[str, Any]:
        """异步启动割草。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return await self.api.async_send_command(device_id, MowerCommand.START)

    def start_mowing(self, device_id: str) -> dict[str, Any]:
        """同步启动割草。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return self.api.send_command(device_id, MowerCommand.START)

    async def async_pause_mowing(self, device_id: str) -> dict[str, Any]:
        """异步暂停割草。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return await self.api.async_send_command(device_id, MowerCommand.PAUSE)

    def pause_mowing(self, device_id: str) -> dict[str, Any]:
        """同步暂停割草。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return self.api.send_command(device_id, MowerCommand.PAUSE)

    async def async_dock(self, device_id: str) -> dict[str, Any]:
        """异步返回充电站。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return await self.api.async_send_command(device_id, MowerCommand.DOCK)

    def dock(self, device_id: str) -> dict[str, Any]:
        """同步返回充电站。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return self.api.send_command(device_id, MowerCommand.DOCK)

    async def async_resume(self, device_id: str) -> dict[str, Any]:
        """异步恢复割草。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return await self.api.async_send_command(device_id, MowerCommand.RESUME)

    def resume(self, device_id: str) -> dict[str, Any]:
        """同步恢复割草。

        Args:
            device_id: 设备 ID

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果指令执行失败
        """
        return self.api.send_command(device_id, MowerCommand.RESUME)

    def get_cached_status(self, device_id: str) -> DeviceStatus | None:
        """获取缓存的设备状态。

        Args:
            device_id: 设备 ID

        Returns:
            设备状态，如果不存在则返回 None
        """
        return self.mqtt.get_cached_status(device_id)

    async def async_get_device_status(self, device_id: str) -> DeviceStatus:
        """异步获取设备状态（通过 API）。

        Args:
            device_id: 设备 ID

        Returns:
            设备状态

        Raises:
            MowerAPIError: 如果请求失败
        """
        return await self.api.async_get_device_status(device_id)

    async def async_get_device_statuses(
        self, device_ids: list[str]
    ) -> dict[str, DeviceStatus]:
        """批量异步获取设备状态（通过 API）。

        Args:
            device_ids: 设备 ID 列表

        Returns:
            设备 ID 到状态的映射

        Raises:
            MowerAPIError: 如果请求失败
        """
        return await self.api.async_get_device_statuses(device_ids)

    def get_device_status(self, device_id: str) -> DeviceStatus:
        """同步获取设备状态（通过 API）。

        Args:
            device_id: 设备 ID

        Returns:
            设备状态

        Raises:
            MowerAPIError: 如果请求失败
        """
        return self.api.get_device_status(device_id)

    def get_device_statuses(self, device_ids: list[str]) -> dict[str, DeviceStatus]:
        """批量同步获取设备状态（通过 API）。

        Args:
            device_ids: 设备 ID 列表

        Returns:
            设备 ID 到状态的映射

        Raises:
            MowerAPIError: 如果请求失败
        """
        return asyncio.run(self.api.async_get_device_statuses(device_ids))

    def get_token(self) -> str:
        """Get the current access token.

        获取当前访问令牌。
        """
        return self._token
