"""REST API 客户端模块。

提供与割草机平台 REST API 交互的功能。
"""

import asyncio
import uuid
from typing import Any

import aiohttp

from mower_sdk.errors import MowerAPIError, ERROR_MESSAGES
from mower_sdk.models import Device, DeviceStatus, MowerCommand


class MowerAPI:
    """REST API 客户端。

    提供与割草机平台 API 交互的同步和异步接口。

    Attributes:
        base_url: API 基础 URL（TODO: 需要配置实际的 API 基础 URL）
        session: aiohttp 会话（异步）
        token: 访问令牌
    """

    def __init__(self, session: aiohttp.ClientSession, token: str, base_url: str):
        """初始化 API 客户端。

        Args:
            session: aiohttp 会话
            token: 访问令牌
            base_url: API 基础 URL
        """
        self.base_url = base_url.rstrip("/")
        self._session = session
        self._token = token

    def set_token(self, token: str) -> None:
        """更新访问令牌。"""
        self._token = token

    def _get_auth_headers(self) -> dict[str, str]:
        """获取认证头。"""
        if not self._token:
            raise MowerAPIError(
                ERROR_MESSAGES["TOKEN_EXPIRED"],
                status_code=401,
                error_code="TOKEN_EXPIRED",
            )
        return {"Authorization": f"Bearer {self._token}"}

    async def _async_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """发送异步 HTTP 请求。

        Args:
            method: HTTP 方法（GET, POST, PUT, DELETE）
            endpoint: API 端点（相对路径）
            data: 请求体数据（可选）
            params: 查询参数（可选）

        Returns:
            响应 JSON 数据

        Raises:
            MowerAPIError: 如果请求失败
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_auth_headers()
        headers["requestId"] = str(uuid.uuid4())

        try:
            session = self._session
            async with session.request(
                method, url, json=data, params=params, headers=headers
            ) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise MowerAPIError(
                        f"{ERROR_MESSAGES['API_REQUEST_FAILED']}: {error_text}",
                        status_code=response.status,
                    )

                return await response.json()
        except aiohttp.ClientError as e:
            raise MowerAPIError(
                f"{ERROR_MESSAGES['API_REQUEST_FAILED']}: {str(e)}"
            ) from e

    async def async_get_devices(self) -> list[Device]:
        """异步获取设备列表。

        Returns:
            设备列表

        Raises:
            MowerAPIError: 如果请求失败
        """
        response = await self._async_request("GET", "/openapi/smarthome/authList")
        if response.get("code") != 1:
            raise MowerAPIError(
                f"{ERROR_MESSAGES['API_REQUEST_FAILED']}: {response.get('desc')}"
            )
        payload = response.get("data", {}).get("payload", {})
        devices_data = payload.get("devices", [])
        return [Device.from_dict(device_data) for device_data in devices_data]

    async def async_get_mqtt_user_info(self) -> dict[str, Any]:
        """异步获取 MQTT 连接信息。

        Returns:
            MQTT 连接信息数据

        Raises:
            MowerAPIError: 如果请求失败
        """
        response = await self._async_request("GET", "/openapi/mqtt/userInfo/get/v2")
        if response.get("code") != 1:
            raise MowerAPIError(
                f"{ERROR_MESSAGES['API_REQUEST_FAILED']}: {response.get('desc')}"
            )
        return response.get("data", {})

    def get_devices(self) -> list[Device]:
        """同步获取设备列表。

        Returns:
            设备列表

        Raises:
            MowerAPIError: 如果请求失败
        """
        return asyncio.run(self.async_get_devices())

    def get_mqtt_user_info(self) -> dict[str, Any]:
        """同步获取 MQTT 连接信息。"""
        return asyncio.run(self.async_get_mqtt_user_info())

    async def async_get_device_statuses(
        self, device_ids: list[str]
    ) -> dict[str, DeviceStatus]:
        """批量异步获取设备状态。

        Args:
            device_ids: 设备 ID 列表

        Returns:
            设备 ID 到状态的映射

        Raises:
            MowerAPIError: 如果请求失败
        """
        if not device_ids:
            return {}
        response = await self._async_request(
            "POST",
            "/openapi/smarthome/getVehicleStatus",
            data={"devices": [{"id": device_id} for device_id in device_ids]},
        )
        if response.get("code") != 1:
            raise MowerAPIError(
                f"{ERROR_MESSAGES['API_REQUEST_FAILED']}: {response.get('desc')}"
            )
        payload = response.get("data", {}).get("payload", {})
        devices_data = payload.get("devices", [])
        result: dict[str, DeviceStatus] = {}
        for status_data in devices_data:
            status = DeviceStatus.from_dict(status_data)
            if status.device_id:
                result[status.device_id] = status
        return result

    async def async_get_device_status(self, device_id: str) -> DeviceStatus:
        """异步获取设备状态。

        Args:
            device_id: 设备 ID

        Returns:
            设备状态

        Raises:
            MowerAPIError: 如果请求失败或设备未找到
        """
        try:
            statuses = await self.async_get_device_statuses([device_id])
            status = statuses.get(device_id)
            if not status:
                raise MowerAPIError(
                    ERROR_MESSAGES["DEVICE_NOT_FOUND"],
                    status_code=404,
                    error_code="DEVICE_NOT_FOUND",
                )
            return status
        except MowerAPIError as e:
            if e.status_code == 404:
                raise MowerAPIError(
                    ERROR_MESSAGES["DEVICE_NOT_FOUND"],
                    status_code=404,
                    error_code="DEVICE_NOT_FOUND",
                ) from e
            raise

    def get_device_status(self, device_id: str) -> DeviceStatus:
        """同步获取设备状态。

        Args:
            device_id: 设备 ID

        Returns:
            设备状态

        Raises:
            MowerAPIError: 如果请求失败或设备未找到
        """
        return asyncio.run(self.async_get_device_status(device_id))

    async def async_send_command(
        self, device_id: str, command: MowerCommand
    ) -> dict[str, Any]:
        """异步发送控制指令。

        Args:
            device_id: 设备 ID
            command: 控制指令

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果请求失败或指令执行失败
        """
        command_mapping: dict[MowerCommand, tuple[str, dict[str, Any] | None]] = {
            MowerCommand.START: (
                "action.devices.commands.StartStop",
                {"on": True},
            ),
            MowerCommand.STOP: (
                "action.devices.commands.StartStop",
                {"on": False},
            ),
            MowerCommand.PAUSE: (
                "action.devices.commands.PauseUnpause",
                {"on": False},
            ),
            MowerCommand.RESUME: (
                "action.devices.commands.PauseUnpause",
                {"on": True},
            ),
            MowerCommand.DOCK: ("action.devices.commands.Dock", None),
        }
        if command not in command_mapping:
            raise MowerAPIError(
                ERROR_MESSAGES["INVALID_COMMAND"],
                error_code="INVALID_COMMAND",
            )
        command_name, params = command_mapping[command]
        execution: dict[str, Any] = {"command": command_name}
        if params is not None:
            execution["params"] = params

        response = await self._async_request(
            "POST",
            "/openapi/smarthome/sendCommands",
            data={
                "commands": [
                    {"devices": [{"id": device_id}], "execution": execution}
                ]
            },
        )
        if response.get("code") != 1:
            raise MowerAPIError(
                f"{ERROR_MESSAGES['API_REQUEST_FAILED']}: {response.get('desc')}"
            )
        payload = response.get("data", {}).get("payload", {})
        command_results = payload.get("commands", [])
        for result in command_results:
            if result.get("status") == "ERROR":
                error_code = result.get("errorCode") or "COMMAND_FAILED"
                # 设备已处于目标状态时视为成功，避免重复点击或状态不同步时报错
                if error_code == "alreadyInState":
                    continue
                raise MowerAPIError(
                    f"{ERROR_MESSAGES['COMMAND_FAILED']}: {error_code}",
                    error_code=error_code,
                )
        return response.get("data", {})

    def send_command(
        self, device_id: str, command: MowerCommand
    ) -> dict[str, Any]:
        """同步发送控制指令。

        Args:
            device_id: 设备 ID
            command: 控制指令

        Returns:
            指令执行结果

        Raises:
            MowerAPIError: 如果请求失败或指令执行失败
        """
        return asyncio.run(self.async_send_command(device_id, command))

    async def async_query_command_results(
        self, devices: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        """异步查询指令执行结果。

        Args:
            devices: 指令设备列表，包含 id 与 cmdNum

        Returns:
            指令执行结果列表

        Raises:
            MowerAPIError: 如果请求失败
        """
        if not devices:
            return []
        response = await self._async_request(
            "POST",
            "/openapi/smarthome/responseCommands",
            data={"devices": devices},
        )
        if response.get("code") != 1:
            raise MowerAPIError(
                f"{ERROR_MESSAGES['API_REQUEST_FAILED']}: {response.get('desc')}"
            )
        payload = response.get("data", {}).get("payload", {})
        return payload.get("devices", [])

    def query_command_results(self, devices: list[dict[str, str]]) -> list[dict[str, Any]]:
        """同步查询指令执行结果。"""
        return asyncio.run(self.async_query_command_results(devices))

    def __del__(self):
        """清理资源。"""
        if hasattr(self, "_session") and self._session and not self._session.closed:
            # 注意：在 __del__ 中不能使用 await，这里只是尝试关闭
            # 更好的做法是使用上下文管理器或显式调用 close 方法
            pass
