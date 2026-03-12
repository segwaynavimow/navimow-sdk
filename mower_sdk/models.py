"""数据模型模块。

定义 SDK 中使用的所有数据模型，包括枚举类型和数据类。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


_RAW_STATE_TO_CANONICAL: dict[str, str] = {
    "isDocked": "docked",
    "isIdel": "idle",
    "isIdle": "idle",
    "isMapping": "mowing",
    "isRunning": "mowing",
    "isPaused": "paused",
    "isDocking": "returning",
    "Error": "error",
    "error": "error",
    "isLifted": "error",
    "inSoftwareUpdate": "paused",
    "Self-Checking": "idle",
    "Self-checking": "idle",
    "Offline": "unknown",
    "offline": "unknown",
}


def _normalize_state_value(raw_state: Any) -> str:
    """Normalize cloud/raw mower state to canonical internal state value."""
    if isinstance(raw_state, MowerStatus):
        return raw_state.value
    if not isinstance(raw_state, str):
        return "unknown"
    return _RAW_STATE_TO_CANONICAL.get(raw_state, raw_state)


def _extract_battery_value(data: dict[str, Any]) -> int:
    """Extract battery percentage from multiple payload formats."""
    def _to_int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # MQTT state payload commonly carries direct battery field.
    battery = _to_int_or_none(data.get("battery"))
    if battery is not None:
        return battery

    # HTTP getVehicleStatus payload uses capacityRemaining[].rawValue.
    capacity_remaining = data.get("capacityRemaining")
    if isinstance(capacity_remaining, list):
        for item in capacity_remaining:
            if not isinstance(item, dict):
                continue
            unit = str(item.get("unit", "")).upper()
            if unit == "PERCENTAGE":
                raw_value = _to_int_or_none(item.get("rawValue"))
                if raw_value is not None:
                    return raw_value

        # Compatibility fallback: if PERCENTAGE unit missing, try first item.
        if capacity_remaining and isinstance(capacity_remaining[0], dict):
            raw_value = _to_int_or_none(capacity_remaining[0].get("rawValue"))
            if raw_value is not None:
                return raw_value

    return 0


class MowerStatus(Enum):
    """割草机状态枚举。"""

    IDLE = "idle"  # 空闲
    MOWING = "mowing"  # 割草中
    PAUSED = "paused"  # 已暂停
    DOCKED = "docked"  # 已回充
    CHARGING = "charging"  # 充电中
    ERROR = "error"  # 错误
    RETURNING = "returning"  # 返回中
    UNKNOWN = "unknown"  # 未知状态


class MowerCommand(Enum):
    """割草机控制指令枚举。"""

    START = "start"  # 开始割草
    PAUSE = "pause"  # 暂停割草
    DOCK = "dock"  # 返回充电站
    RESUME = "resume"  # 恢复割草
    STOP = "stop"  # 停止


class MowerError(Enum):
    """割草机错误类型枚举。"""

    NONE = "none"  # 无错误
    STUCK = "stuck"  # 卡住
    LIFTED = "lifted"  # 被抬起
    RAIN = "rain"  # 雨天
    BATTERY_LOW = "battery_low"  # 电池电量低
    SENSOR_ERROR = "sensor_error"  # 传感器错误
    MOTOR_ERROR = "motor_error"  # 电机错误
    BLADE_ERROR = "blade_error"  # 刀片错误
    UNKNOWN = "unknown"  # 未知错误


@dataclass
class Device:
    """设备信息数据类。

    Attributes:
        id: 设备 ID
        name: 设备名称
        model: 设备型号
        firmware_version: 固件版本
        serial_number: 序列号
        mac_address: MAC 地址（可选）
        online: 是否在线
        extra: 额外信息（可选）
    """

    id: str
    name: str
    model: str
    firmware_version: str
    serial_number: str
    mac_address: str | None = None
    online: bool = False
    extra: dict[str, Any] | None = None
    product_key: str | None = None
    device_name: str | None = None
    iot_id: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Device":
        """从字典创建 Device 实例。

        Args:
            data: 包含设备信息的字典

        Returns:
            Device 实例
        """
        product_key = data.get("productKey") or data.get("product_key")
        device_name = data.get("deviceName") or data.get("device_name") or data.get("name")
        iot_id = data.get("iotId") or data.get("iot_id") or data.get("id")

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            model=data.get("model", ""),
            firmware_version=data.get("firmware_version", ""),
            serial_number=data.get("serial_number", ""),
            mac_address=data.get("mac_address"),
            online=data.get("online", False),
            extra=data.get("extra"),
            product_key=product_key,
            device_name=device_name,
            iot_id=iot_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。

        Returns:
            包含设备信息的字典
        """
        result = {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "serial_number": self.serial_number,
            "online": self.online,
        }
        if self.mac_address:
            result["mac_address"] = self.mac_address
        if self.extra:
            result["extra"] = self.extra
        if self.product_key:
            result["product_key"] = self.product_key
        if self.device_name:
            result["device_name"] = self.device_name
        if self.iot_id:
            result["iot_id"] = self.iot_id
        return result


@dataclass
class ThingParams:
    """Common params wrapper for Thing messages."""

    iot_id: str | None = None
    product_key: str | None = None
    device_name: str | None = None
    identifier: str | None = None
    value: Any | None = None
    raw: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThingParams":
        return cls(
            iot_id=data.get("iotId") or data.get("iot_id"),
            product_key=data.get("productKey") or data.get("product_key"),
            device_name=data.get("deviceName") or data.get("device_name"),
            identifier=data.get("identifier"),
            value=data.get("value"),
            raw=data,
        )


@dataclass
class ThingStatusMessage:
    """Thing status message."""

    method: str | None
    id: str | None
    params: ThingParams
    version: str | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ThingStatusMessage":
        return cls(
            method=payload.get("method"),
            id=payload.get("id"),
            params=ThingParams.from_dict(payload.get("params", {})),
            version=payload.get("version"),
        )


@dataclass
class ThingPropertiesMessage:
    """Thing properties message."""

    method: str | None
    id: str | None
    params: ThingParams
    version: str | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ThingPropertiesMessage":
        return cls(
            method=payload.get("method"),
            id=payload.get("id"),
            params=ThingParams.from_dict(payload.get("params", {})),
            version=payload.get("version"),
        )


@dataclass
class ThingEventMessage:
    """Thing event message."""

    method: str | None
    id: str | None
    params: ThingParams
    version: str | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ThingEventMessage":
        return cls(
            method=payload.get("method"),
            id=payload.get("id"),
            params=ThingParams.from_dict(payload.get("params", {})),
            version=payload.get("version"),
        )


@dataclass
class DeviceStatus:
    """设备状态数据类。

    Attributes:
        device_id: 设备 ID
        status: 设备状态（MowerStatus 枚举值）
        battery: 电池电量（0-100）
        position: 位置信息（可选，格式：{"lat": float, "lng": float}）
        error_code: 错误代码（MowerError 枚举值）
        error_message: 错误消息（可选）
        mowing_time: 本次割草时长（秒，可选）
        total_mowing_time: 总割草时长（秒，可选）
        signal_strength: 信号强度（可选）
        timestamp: 状态更新时间戳（可选）
        extra: 额外信息（可选）
    """

    device_id: str
    status: MowerStatus
    battery: int
    position: dict[str, float] | None = None
    error_code: MowerError = MowerError.NONE
    error_message: str | None = None
    mowing_time: int | None = None
    total_mowing_time: int | None = None
    signal_strength: int | None = None
    timestamp: int | None = None
    extra: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceStatus":
        """从字典创建 DeviceStatus 实例。

        Args:
            data: 包含设备状态的字典

        Returns:
            DeviceStatus 实例
        """
        status_source = data.get("status") or data.get("state") or data.get("vehicleState")
        normalized_state = _normalize_state_value(status_source)
        try:
            status = MowerStatus(normalized_state)
        except ValueError:
            status = MowerStatus.UNKNOWN

        error_str = data.get("error_code", "none")
        try:
            error_code = MowerError(error_str)
        except ValueError:
            error_code = MowerError.UNKNOWN

        battery = _extract_battery_value(data)

        extra = data.get("extra") or {}
        if "vehicleState" in data:
            extra["vehicleState"] = data.get("vehicleState")
        if "descriptiveCapacityRemaining" in data:
            extra["descriptiveCapacityRemaining"] = data.get(
                "descriptiveCapacityRemaining"
            )
        if "capacityRemaining" in data:
            extra["capacityRemaining"] = data.get("capacityRemaining")
        if not extra:
            extra = None

        return cls(
            device_id=data.get("device_id") or data.get("id", ""),
            status=status,
            battery=battery,
            position=data.get("position"),
            error_code=error_code,
            error_message=data.get("error_message"),
            mowing_time=data.get("mowing_time"),
            total_mowing_time=data.get("total_mowing_time"),
            signal_strength=data.get("signal_strength"),
            timestamp=data.get("timestamp"),
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。

        Returns:
            包含设备状态的字典
        """
        result = {
            "device_id": self.device_id,
            "status": self.status.value,
            "battery": self.battery,
            "error_code": self.error_code.value,
        }
        if self.position:
            result["position"] = self.position
        if self.error_message:
            result["error_message"] = self.error_message
        if self.mowing_time is not None:
            result["mowing_time"] = self.mowing_time
        if self.total_mowing_time is not None:
            result["total_mowing_time"] = self.total_mowing_time
        if self.signal_strength is not None:
            result["signal_strength"] = self.signal_strength
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp
        if self.extra:
            result["extra"] = self.extra
        return result


@dataclass
class DeviceStateMessage:
    """Unified state message from MQTT."""

    device_id: str
    timestamp: int | None
    state: str
    battery: int | None = None
    signal_strength: int | None = None
    position: dict[str, float] | None = None
    error: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeviceStateMessage":
        raw_state = payload.get("state") or payload.get("status") or payload.get(
            "vehicleState"
        )
        normalized_state = _normalize_state_value(raw_state)
        metrics = payload.get("metrics")
        if not isinstance(metrics, dict):
            metrics = dict(metrics or {})
        if raw_state is not None and normalized_state != raw_state:
            metrics["raw_state"] = raw_state

        return cls(
            device_id=payload.get("device_id", ""),
            timestamp=payload.get("timestamp"),
            state=normalized_state,
            battery=_extract_battery_value(payload),
            signal_strength=payload.get("signal_strength"),
            position=payload.get("position"),
            error=payload.get("error"),
            metrics=metrics or None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "state": self.state,
            "battery": self.battery,
            "signal_strength": self.signal_strength,
            "position": self.position,
            "error": self.error,
            "metrics": self.metrics,
        }


@dataclass
class DeviceEventMessage:
    """Unified event message from MQTT."""

    device_id: str
    timestamp: int | None
    type: str
    event: str
    level: str | None = None
    message: str | None = None
    params: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeviceEventMessage":
        return cls(
            device_id=payload.get("device_id", ""),
            timestamp=payload.get("timestamp"),
            type=payload.get("type", "system"),
            event=payload.get("event", ""),
            level=payload.get("level"),
            message=payload.get("message"),
            params=payload.get("params"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "type": self.type,
            "event": self.event,
            "level": self.level,
            "message": self.message,
            "params": self.params,
        }


@dataclass
class DeviceAttributesMessage:
    """Unified attributes message from MQTT."""

    device_id: str
    attributes: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeviceAttributesMessage":
        return cls(
            device_id=payload.get("device_id", ""),
            attributes=payload.get("attributes", {}) or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "attributes": self.attributes,
        }


@dataclass
class DeviceCommandMessage:
    """Unified command message for MQTT publish."""

    id: str
    device_id: str
    command: str
    params: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeviceCommandMessage":
        return cls(
            id=payload.get("id", ""),
            device_id=payload.get("device_id", ""),
            command=payload.get("command", ""),
            params=payload.get("params"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "command": self.command,
            "params": self.params or {},
        }
