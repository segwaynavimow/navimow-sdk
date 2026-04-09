"""MQTT 客户端模块。

提供 MQTT 连接、订阅和设备状态更新功能。
"""

import asyncio
import json
import logging
import uuid
from urllib.parse import urlparse
from collections.abc import Awaitable, Callable
from typing import Any

from paho.mqtt import client as mqtt_client

from mower_sdk.errors import MowerMQTTError, ERROR_MESSAGES
from mower_sdk.models import Device, DeviceStatus
from mower_sdk.utils import parse_json

_LOGGER = logging.getLogger(__name__)


def _build_web_client_id(username: str | None) -> str:
    base = username or "unknown"
    rand = uuid.uuid4().hex[:10]
    return f"web_{base}_{rand}"


def _mask_secret(value: str | None) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def _format_auth_headers(headers: dict[str, str] | None) -> str:
    if not headers:
        return "<none>"
    safe = {}
    for key, val in headers.items():
        if key.lower() == "authorization":
            safe[key] = _mask_secret(val)
        else:
            safe[key] = val
    return str(safe)


class MowerMQTT:
    """MQTT 客户端。

    提供 MQTT 连接、订阅和设备状态更新功能，支持同步和异步接口。

    Attributes:
        broker: MQTT broker 地址
        port: MQTT broker 端口
        username: MQTT 用户名（可选）
        password: MQTT 密码（可选）
        status_cache: 设备状态缓存
        _async_client: 异步 MQTT 客户端
        _sync_client: 同步 MQTT 客户端
        _callbacks: 回调函数字典
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        ws_path: str | None = None,
        auth_headers: dict[str, str] | None = None,
        keepalive_seconds: int = 2400,
        reconnect_min_delay: int = 1,
        reconnect_max_delay: int = 60,
    ):
        """初始化 MQTT 客户端。

        Args:
            broker: MQTT broker 地址
            port: MQTT broker 端口
            username: MQTT 用户名（可选）
            password: MQTT 密码（可选）
        """
        self.broker = broker
        self.port = port
        self.username = username
        self.password = password
        self.ws_path = ws_path
        self.auth_headers = auth_headers
        # KeepAlive 是 MQTT 协议层保活（PINGREQ/PINGRESP），优先于应用层“心跳消息”。
        # 这里默认 40 分钟，确保在“1 小时无流量断连”的 broker/LB 前有协议层流量。
        self.keepalive_seconds = max(30, int(keepalive_seconds))
        self.reconnect_min_delay = max(0, int(reconnect_min_delay))
        self.reconnect_max_delay = max(self.reconnect_min_delay, int(reconnect_max_delay))
        self._use_tls = bool(ws_path)
        self._client_id = _build_web_client_id(self.username)
        self.status_cache: dict[str, DeviceStatus] = {}
        self._async_client: mqtt_client.Client | None = None
        self._sync_client: mqtt_client.Client | None = None
        self._async_stop_event: asyncio.Event | None = None
        self._callbacks: dict[str, dict[str, Callable]] = {}
        self._connected = False

    def configure_wss(
        self,
        mqtt_host: str,
        mqtt_url: str,
        username: str | None,
        password: str | None,
        auth_headers: dict[str, str] | None,
        port: int = 443,
    ) -> None:
        """配置 WSS 连接参数。"""
        parsed = urlparse(mqtt_host)
        host = parsed.hostname or mqtt_host
        self.broker = host
        self.port = parsed.port or port
        self.ws_path = mqtt_url
        self.username = username
        self.password = password
        self.auth_headers = auth_headers
        self._use_tls = True

    def _build_client(self) -> mqtt_client.Client:
        transport = "websockets" if self.ws_path else "tcp"
        client = mqtt_client.Client(client_id=self._client_id, transport=transport)
        if self.username and self.password:
            client.username_pw_set(self.username, self.password)
        if self.ws_path:
            client.ws_set_options(path=self.ws_path, headers=self.auth_headers or {})
        if self._use_tls:
            client.tls_set()
        # 断线自动重连退避（paho 在 loop_start + connect_async 场景下会按该策略重连）
        client.reconnect_delay_set(
            min_delay=self.reconnect_min_delay, max_delay=self.reconnect_max_delay
        )
        _LOGGER.debug(
            "MQTT client built: transport=%s broker=%s port=%s ws_path=%s tls=%s client_id=%s",
            transport,
            self.broker,
            self.port,
            self.ws_path,
            self._use_tls,
            self._client_id,
        )
        return client

    def _get_status_topic(self, device_id: str) -> str:
        """获取设备状态 topic。

        Args:
            device_id: 设备 ID

        Returns:
            Topic 路径
        """
        # TODO: 根据实际 MQTT topic 格式调整
        return f"device/{device_id}/status"

    def _get_event_topic(self, device_id: str) -> str:
        """获取设备事件 topic。

        Args:
            device_id: 设备 ID

        Returns:
            Topic 路径
        """
        # TODO: 根据实际 MQTT topic 格式调整
        return f"device/{device_id}/event"

    async def async_connect(self) -> None:
        """异步连接 MQTT broker。

        Raises:
            MowerMQTTError: 如果连接失败
        """
        try:
            # 连接在订阅时执行，这里仅确保配置有效
            self._connected = True
        except Exception as e:
            raise MowerMQTTError(
                f"{ERROR_MESSAGES['MQTT_CONNECTION_FAILED']}: {str(e)}"
            ) from e

    def connect(self) -> None:
        """同步连接 MQTT broker。

        Raises:
            MowerMQTTError: 如果连接失败
        """
        try:
            self._sync_client = self._build_client()
            _LOGGER.info(
                "MQTT connect details (sync): transport=%s broker=%s port=%s ws_path=%s tls=%s username=%s auth_headers=%s",
                "websockets" if self.ws_path else "tcp",
                self.broker,
                self.port,
                self.ws_path,
                self._use_tls,
                _mask_secret(self.username),
                _format_auth_headers(self.auth_headers),
            )

            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    self._connected = True
                    _LOGGER.info(
                        "MQTT connected (sync): broker=%s port=%s",
                        self.broker,
                        self.port,
                    )
                else:
                    raise MowerMQTTError(
                        f"{ERROR_MESSAGES['MQTT_CONNECTION_FAILED']}: Return code {rc}"
                    )

            self._sync_client.on_connect = on_connect
            _LOGGER.info(
                "MQTT connecting (sync): broker=%s port=%s ws_path=%s",
                self.broker,
                self.port,
                self.ws_path,
            )
            self._sync_client.connect(self.broker, self.port, self.keepalive_seconds)
            self._sync_client.loop_start()
        except Exception as e:
            raise MowerMQTTError(
                f"{ERROR_MESSAGES['MQTT_CONNECTION_FAILED']}: {str(e)}"
            ) from e

    async def async_subscribe_device(
        self,
        device_id: str,
        on_status_update: Callable[[DeviceStatus], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """异步订阅设备状态和事件。

        Args:
            device_id: 设备 ID
            on_status_update: 状态更新回调函数
            on_event: 事件回调函数

        Raises:
            MowerMQTTError: 如果订阅失败
        """
        status_topic = self._get_status_topic(device_id)
        event_topic = self._get_event_topic(device_id)

        # 保存回调函数
        self._callbacks[device_id] = {
            "status": on_status_update,
            "event": on_event,
        }

        loop = asyncio.get_running_loop()
        self._async_stop_event = asyncio.Event()
        try:
            self._async_client = self._build_client()
            _LOGGER.info(
                "MQTT connect details (async): transport=%s broker=%s port=%s ws_path=%s tls=%s username=%s auth_headers=%s device=%s",
                "websockets" if self.ws_path else "tcp",
                self.broker,
                self.port,
                self.ws_path,
                self._use_tls,
                _mask_secret(self.username),
                _format_auth_headers(self.auth_headers),
                device_id,
            )

            def on_connect(_client, _userdata, _flags, rc) -> None:
                if rc != 0:
                    _LOGGER.error("MQTT connection failed: rc=%s", rc)
                    return
                self._connected = True
                _LOGGER.info(
                    "MQTT connected (async): broker=%s port=%s device=%s",
                    self.broker,
                    self.port,
                    device_id,
                )
                _LOGGER.info(
                    "MQTT subscribing (async): %s, %s",
                    status_topic,
                    event_topic,
                )
                _client.subscribe(status_topic)
                _client.subscribe(event_topic)

            def on_message(_client, _userdata, msg) -> None:
                try:
                    payload_text = (msg.payload or b"").decode("utf-8", errors="replace")
                    _LOGGER.debug(
                        "MQTT payload (async): topic=%s payload=%s",
                        msg.topic,
                        payload_text,
                    )
                    payload = parse_json(msg.payload)
                    topic = msg.topic
                    _LOGGER.debug(
                        "MQTT message (async): topic=%s bytes=%d device=%s",
                        topic,
                        len(msg.payload or b""),
                        device_id,
                    )
                    if topic == status_topic:
                        status = DeviceStatus.from_dict(payload)
                        self.status_cache[device_id] = status
                        callback = self._callbacks.get(device_id, {}).get("status")
                        if callback:
                            loop.call_soon_threadsafe(callback, status)
                    elif topic == event_topic:
                        callback = self._callbacks.get(device_id, {}).get("event")
                        if callback:
                            loop.call_soon_threadsafe(callback, payload)
                except Exception as e:
                    _LOGGER.exception("Error processing MQTT message: %s", e)

            def on_disconnect(_client, _userdata, _rc) -> None:
                _LOGGER.debug(
                    "MQTT disconnected (async): broker=%s port=%s device=%s",
                    self.broker,
                    self.port,
                    device_id,
                )
                if self._async_stop_event:
                    self._async_stop_event.set()

            self._async_client.on_connect = on_connect
            self._async_client.on_message = on_message
            self._async_client.on_disconnect = on_disconnect
            _LOGGER.info(
                "MQTT connecting (async): broker=%s port=%s ws_path=%s device=%s",
                self.broker,
                self.port,
                self.ws_path,
                device_id,
            )
            self._async_client.connect(self.broker, self.port, self.keepalive_seconds)
            self._async_client.loop_start()

            await self._async_stop_event.wait()
        except Exception as e:
            raise MowerMQTTError(
                f"{ERROR_MESSAGES['MQTT_SUBSCRIBE_FAILED']}: {str(e)}"
            ) from e

    def subscribe_device(
        self,
        device_id: str,
        on_status_update: Callable[[DeviceStatus], None] | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        """同步订阅设备状态和事件。

        Args:
            device_id: 设备 ID
            on_status_update: 状态更新回调函数
            on_event: 事件回调函数

        Raises:
            MowerMQTTError: 如果订阅失败
        """
        if not self._sync_client:
            self.connect()

        status_topic = self._get_status_topic(device_id)
        event_topic = self._get_event_topic(device_id)

        def on_message(client, userdata, msg):
            try:
                payload_text = (msg.payload or b"").decode("utf-8", errors="replace")
                _LOGGER.debug(
                    "MQTT payload (sync): topic=%s payload=%s",
                    msg.topic,
                    payload_text,
                )
                payload = parse_json(msg.payload)
                topic = msg.topic
                _LOGGER.debug(
                    "MQTT message (sync): topic=%s bytes=%d device=%s",
                    topic,
                    len(msg.payload or b""),
                    device_id,
                )

                if topic == status_topic:
                    # 处理状态更新
                    status = DeviceStatus.from_dict(payload)
                    self.status_cache[device_id] = status

                    if on_status_update:
                        on_status_update(status)

                elif topic == event_topic:
                    # 处理事件
                    if on_event:
                        on_event(payload)

            except Exception as e:
                # 记录错误但继续处理
                print(f"Error processing MQTT message: {e}")

        try:
            self._sync_client.on_message = on_message
            _LOGGER.info(
                "MQTT subscribing (sync): %s, %s",
                status_topic,
                event_topic,
            )
            self._sync_client.subscribe(status_topic)
            self._sync_client.subscribe(event_topic)

            # 保存回调函数
            self._callbacks[device_id] = {
                "status": on_status_update,
                "event": on_event,
            }
        except Exception as e:
            raise MowerMQTTError(
                f"{ERROR_MESSAGES['MQTT_SUBSCRIBE_FAILED']}: {str(e)}"
            ) from e

    def get_cached_status(self, device_id: str) -> DeviceStatus | None:
        """获取缓存的设备状态。

        Args:
            device_id: 设备 ID

        Returns:
            设备状态，如果不存在则返回 None
        """
        return self.status_cache.get(device_id)

    async def async_disconnect(self) -> None:
        """异步断开 MQTT 连接。"""
        if self._async_client:
            self._async_client.loop_stop()
            self._async_client.disconnect()
        if self._async_stop_event:
            self._async_stop_event.set()
        self._connected = False
        self._async_client = None

    def disconnect(self) -> None:
        """同步断开 MQTT 连接。"""
        if self._sync_client:
            self._sync_client.loop_stop()
            self._sync_client.disconnect()
            self._connected = False


class NavimowMQTT:
    """Navimow MQTT client for cloud topics."""

    def __init__(
        self,
        broker: str,
        port: int,
        username: str | None,
        password: str | None,
        records: list[Device],
        ws_path: str | None = None,
        auth_headers: dict[str, str] | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
        keepalive_seconds: int = 2400,
        reconnect_min_delay: int = 1,
        reconnect_max_delay: int = 60,
    ) -> None:
        parsed = urlparse(broker)
        self.broker = parsed.hostname or broker
        self.port = parsed.port or port
        self.username = username
        self.password = password
        self.records = records
        self.loop = loop or asyncio.get_event_loop()
        self.ws_path = ws_path
        self.auth_headers = auth_headers
        self._use_tls = bool(ws_path) or parsed.scheme == "wss"
        self._client_id = _build_web_client_id(self.username)
        self.keepalive_seconds = max(30, int(keepalive_seconds))
        self.reconnect_min_delay = max(0, int(reconnect_min_delay))
        self.reconnect_max_delay = max(self.reconnect_min_delay, int(reconnect_max_delay))

        self.on_connected: Callable[[], Awaitable[None]] | None = None
        self.on_ready: Callable[[], Awaitable[None]] | None = None
        self.on_message: Callable[[str, bytes, str], Awaitable[None]] | None = None
        self.on_disconnected: Callable[[], Awaitable[None]] | None = None

        transport = "websockets" if self.ws_path else "tcp"
        self.client = mqtt_client.Client(client_id=self._client_id, transport=transport)
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        if self.ws_path:
            self.client.ws_set_options(path=self.ws_path, headers=self.auth_headers or {})
        if self._use_tls:
            self.client.tls_set()
        self.client.reconnect_delay_set(
            min_delay=self.reconnect_min_delay, max_delay=self.reconnect_max_delay
        )

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        _LOGGER.info(
            "NavimowMQTT init: broker=%s port=%s ws_path=%s tls=%s client_id=%s",
            self.broker,
            self.port,
            self.ws_path,
            self._use_tls,
            self._client_id,
        )

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected()

    def _build_new_client(self) -> mqtt_client.Client:
        """重建 paho MQTT client，使用当前最新的凭据和配置。"""
        transport = "websockets" if self.ws_path else "tcp"
        client = mqtt_client.Client(client_id=self._client_id, transport=transport)
        if self.username and self.password:
            client.username_pw_set(self.username, self.password)
        if self.ws_path:
            client.ws_set_options(path=self.ws_path, headers=self.auth_headers or {})
        if self._use_tls:
            client.tls_set()
        client.reconnect_delay_set(
            min_delay=self.reconnect_min_delay, max_delay=self.reconnect_max_delay
        )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        return client

    def update_credentials(
        self,
        username: str | None = None,
        password: str | None = None,
        auth_headers: dict[str, str] | None = None,
    ) -> None:
        """更新 MQTT 凭据。若当前已连接，只更新存储值，待下次重连时生效；若已断开，则立即重连。

        paho-mqtt 的 ws_set_options 只在建立连接前有效，因此重连时需要重建 client。
        已连接时不主动断开，避免因 OAuth token 轮换导致每小时强制断连。
        """
        changed = False
        if username is not None and username != self.username:
            self.username = username
            changed = True
        if password is not None and password != self.password:
            self.password = password
            changed = True
        if auth_headers is not None and auth_headers != self.auth_headers:
            self.auth_headers = auth_headers
            changed = True

        if not changed:
            return

        if self.client.is_connected():
            # 当前连接正常，新凭据已存储，待 broker 下次断连后重连时自动生效。
            # 不主动断开，避免 token 每小时轮换触发不必要的重连和"设备不可用"。
            _LOGGER.info(
                "NavimowMQTT credentials updated while connected (will apply on next reconnect): broker=%s port=%s",
                self.broker,
                self.port,
            )
            return

        # 当前已断开，立即用新凭据重建 client 并重连。
        _LOGGER.info(
            "NavimowMQTT credentials updated while disconnected, rebuilding and reconnecting: broker=%s port=%s",
            self.broker,
            self.port,
        )
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

        self.client = self._build_new_client()
        self.connect_async()

    def connect_async(self) -> None:
        if not self.is_connected:
            _LOGGER.info(
                "NavimowMQTT connect details: transport=%s broker=%s port=%s ws_path=%s tls=%s username=%s auth_headers=%s",
                "websockets" if self.ws_path else "tcp",
                self.broker,
                self.port,
                self.ws_path,
                self._use_tls,
                _mask_secret(self.username),
                _format_auth_headers(self.auth_headers),
            )
            _LOGGER.info(
                "NavimowMQTT connecting: broker=%s port=%s ws_path=%s",
                self.broker,
                self.port,
                self.ws_path,
            )
            self.client.connect_async(self.broker, self.port, self.keepalive_seconds)
            self.client.loop_start()

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
        _LOGGER.info(
            "NavimowMQTT disconnect requested: broker=%s port=%s",
            self.broker,
            self.port,
        )

    def _get_device_ids(self) -> list[str]:
        device_ids: list[str] = []
        for device in self.records:
            device_id = getattr(device, "id", None)
            if device_id:
                device_ids.append(device_id)
        return device_ids

    def subscribe_all(self, product_key: str, device_name: str) -> None:
        device_ids = self._get_device_ids()
        if not device_ids:
            _LOGGER.warning(
                "NavimowMQTT subscribing cloud topics with wildcard: no device ids available"
            )
            self.client.subscribe("/downlink/vehicle/+/realtimeDate/state")
            self.client.subscribe("/downlink/vehicle/+/realtimeDate/event")
            self.client.subscribe("/downlink/vehicle/+/realtimeDate/attributes")
            return

        _LOGGER.info(
            "NavimowMQTT subscribing cloud topics for %d device(s)", len(device_ids)
        )
        for device_id in device_ids:
            self.client.subscribe(f"/downlink/vehicle/{device_id}/realtimeDate/state")
            self.client.subscribe(f"/downlink/vehicle/{device_id}/realtimeDate/event")
            self.client.subscribe(
                f"/downlink/vehicle/{device_id}/realtimeDate/attributes"
            )

    def unsubscribe_all(self, product_key: str, device_name: str) -> None:
        device_ids = self._get_device_ids()
        if not device_ids:
            _LOGGER.info("NavimowMQTT unsubscribing cloud topics (wildcard)")
            self.client.unsubscribe("/downlink/vehicle/+/realtimeDate/state")
            self.client.unsubscribe("/downlink/vehicle/+/realtimeDate/event")
            self.client.unsubscribe("/downlink/vehicle/+/realtimeDate/attributes")
            return

        _LOGGER.info(
            "NavimowMQTT unsubscribing cloud topics for %d device(s)", len(device_ids)
        )
        for device_id in device_ids:
            self.client.unsubscribe(f"/downlink/vehicle/{device_id}/realtimeDate/state")
            self.client.unsubscribe(f"/downlink/vehicle/{device_id}/realtimeDate/event")
            self.client.unsubscribe(
                f"/downlink/vehicle/{device_id}/realtimeDate/attributes"
            )

    def _schedule(self, coro: Awaitable[None]) -> None:
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(asyncio.create_task, coro)
        else:
            _LOGGER.debug("Event loop not running, skip scheduling MQTT callback")

    def _on_connect(self, _client, _userdata, _flags, rc) -> None:
        if rc != 0:
            _LOGGER.error("MQTT connection failed: rc=%s", rc)
            return
        _LOGGER.info(
            "NavimowMQTT connected: broker=%s port=%s",
            self.broker,
            self.port,
        )
        self.subscribe_all("", "")

        if self.on_connected is not None:
            self._schedule(self.on_connected())
        if self.on_ready is not None:
            self._schedule(self.on_ready())

    def _on_disconnect(self, _client, _userdata, _rc) -> None:
        _LOGGER.debug(
            "NavimowMQTT disconnected: broker=%s port=%s rc=%s",
            self.broker,
            self.port,
            _rc,
        )
        if self.on_disconnected is not None:
            self._schedule(self.on_disconnected())

    def _parse_topic(self, topic: str) -> tuple[str | None, str | None]:
        parts = topic.split("/")
        if parts and parts[0] == "":
            parts = parts[1:]
        if len(parts) != 5:
            return None, None
        if parts[0] != "downlink" or parts[1] != "vehicle":
            return None, None
        if parts[3] != "realtimeDate":
            return None, None
        return parts[2], parts[4]

    def _on_message(self, _client, _userdata, msg) -> None:
        topic = msg.topic
        device_id, _channel = self._parse_topic(topic)

        payload_bytes = msg.payload
        _LOGGER.debug(
            "NavimowMQTT payload: topic=%s payload=%s",
            topic,
            (payload_bytes or b"").decode("utf-8", errors="replace"),
        )
        _LOGGER.debug(
            "NavimowMQTT message: topic=%s bytes=%d device=%s",
            topic,
            len(payload_bytes or b""),
            device_id,
        )
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = None

        if isinstance(payload, dict) and device_id:
            payload.setdefault("device_id", device_id)
            payload_bytes = json.dumps(payload).encode("utf-8")

        if self.on_message is not None and device_id:
            self._schedule(self.on_message(topic, payload_bytes, device_id))

    def publish_command(self, device_id: str, payload: dict[str, Any]) -> None:
        topic = f"navimow/{device_id}/command"
        self.client.publish(topic, json.dumps(payload))
