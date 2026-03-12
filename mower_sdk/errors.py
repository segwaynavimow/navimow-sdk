"""自定义异常类模块。

提供 SDK 中使用的所有自定义异常类型。
"""


class MowerAPIError(Exception):
    """API 请求相关的异常。

    Attributes:
        status_code: HTTP 状态码（如果可用）
        message: 错误消息
        error_code: 业务错误码（如果可用）
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
    ):
        """初始化 API 异常。

        Args:
            message: 错误消息
            status_code: HTTP 状态码
            error_code: 业务错误码
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

    def __str__(self) -> str:
        """返回格式化的错误消息。"""
        parts = [self.message]
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        if self.error_code:
            parts.append(f"Error Code: {self.error_code}")
        return " | ".join(parts)


class MowerAuthError(Exception):
    """认证相关的异常。

    Attributes:
        message: 错误消息
    """

    def __init__(self, message: str):
        """初始化认证异常。

        Args:
            message: 错误消息
        """
        super().__init__(message)
        self.message = message


class MowerMQTTError(Exception):
    """MQTT 相关的异常。

    Attributes:
        message: 错误消息
    """

    def __init__(self, message: str):
        """初始化 MQTT 异常。

        Args:
            message: 错误消息
        """
        super().__init__(message)
        self.message = message


# 错误消息字典
ERROR_MESSAGES = {
    "AUTH_FAILED": "认证失败，请检查 client_id 和 client_secret",
    "TOKEN_EXPIRED": "Token 已过期，请重新登录",
    "TOKEN_REFRESH_FAILED": "Token 刷新失败",
    "DEVICE_NOT_FOUND": "设备未找到",
    "DEVICE_OFFLINE": "设备离线",
    "COMMAND_FAILED": "指令执行失败",
    "API_REQUEST_FAILED": "API 请求失败",
    "MQTT_CONNECTION_FAILED": "MQTT 连接失败",
    "MQTT_SUBSCRIBE_FAILED": "MQTT 订阅失败",
    "INVALID_COMMAND": "无效的指令",
    "INVALID_DEVICE_STATUS": "无效的设备状态",
}

# 指令错误映射
COMMAND_ERRORS = {
    "START": {
        "DEVICE_OFFLINE": "设备离线，无法启动",
        "ALREADY_MOWING": "设备正在割草中",
        "BATTERY_LOW": "电池电量过低，无法启动",
    },
    "PAUSE": {
        "NOT_MOWING": "设备未在割草中，无法暂停",
        "DEVICE_OFFLINE": "设备离线，无法暂停",
    },
    "DOCK": {
        "ALREADY_DOCKED": "设备已在充电站",
        "DEVICE_OFFLINE": "设备离线，无法返回充电站",
    },
    "RESUME": {
        "NOT_PAUSED": "设备未暂停，无法恢复",
        "DEVICE_OFFLINE": "设备离线，无法恢复",
    },
}
