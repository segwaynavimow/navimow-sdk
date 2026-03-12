"""割草机平台 Python SDK。

提供与云端割草机平台交互的功能，包括 REST API 和 MQTT 支持。
"""

from mower_sdk.api import MowerAPI
from mower_sdk.client import MowerClient
from mower_sdk.cloud import NavimowCloud
from mower_sdk.device import NavimowCloudDevice
from mower_sdk.event import DataEvent
from mower_sdk.errors import (
    MowerAPIError,
    MowerAuthError,
    MowerMQTTError,
    ERROR_MESSAGES,
    COMMAND_ERRORS,
)
from mower_sdk.models import (
    Device,
    DeviceAttributesMessage,
    DeviceCommandMessage,
    DeviceEventMessage,
    DeviceStateMessage,
    DeviceStatus,
    MowerCommand,
    MowerError,
    MowerStatus,
    ThingEventMessage,
    ThingPropertiesMessage,
    ThingStatusMessage,
)
from mower_sdk.mqtt import MowerMQTT, NavimowMQTT
from mower_sdk.navimow import Navimow
from mower_sdk.sdk import NavimowSDK
from mower_sdk.state_manager import StateManager

__version__ = "0.1.0"

__all__ = [
    # 主客户端
    "MowerClient",
    "Navimow",
    "NavimowSDK",
    # 子模块
    "MowerAPI",
    "MowerMQTT",
    "NavimowMQTT",
    "NavimowCloud",
    "NavimowCloudDevice",
    "StateManager",
    "DataEvent",
    # 数据模型
    "Device",
    "DeviceStateMessage",
    "DeviceEventMessage",
    "DeviceAttributesMessage",
    "DeviceCommandMessage",
    "DeviceStatus",
    "MowerStatus",
    "MowerCommand",
    "MowerError",
    "ThingStatusMessage",
    "ThingPropertiesMessage",
    "ThingEventMessage",
    # 异常
    "MowerAPIError",
    "MowerMQTTError",
    "ERROR_MESSAGES",
    "COMMAND_ERRORS",
]
