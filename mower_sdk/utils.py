"""工具函数模块。

提供 SDK 中使用的各种工具函数。
"""

import json
import logging
from datetime import datetime
from typing import Any


def setup_logger(name: str = "mower_sdk", level: int = logging.INFO) -> logging.Logger:
    """设置并返回日志记录器。

    Args:
        name: 日志记录器名称
        level: 日志级别

    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def parse_json(data: str | bytes) -> dict[str, Any] | list[Any]:
    """解析 JSON 字符串。

    Args:
        data: JSON 字符串或字节

    Returns:
        解析后的字典或列表

    Raises:
        ValueError: 如果 JSON 解析失败
    """
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    return json.loads(data)


def timestamp_to_datetime(timestamp: int) -> datetime:
    """将时间戳转换为 datetime 对象。

    Args:
        timestamp: Unix 时间戳（秒）

    Returns:
        datetime 对象
    """
    return datetime.fromtimestamp(timestamp)


def datetime_to_timestamp(dt: datetime) -> int:
    """将 datetime 对象转换为时间戳。

    Args:
        dt: datetime 对象

    Returns:
        Unix 时间戳（秒）
    """
    return int(dt.timestamp())
