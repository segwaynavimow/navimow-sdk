# Navimow Python SDK

<p align="center">
  <img src="https://fra-navimow-prod.s3.eu-central-1.amazonaws.com/img/navimowhomeassistant.png" width="600">
</p>

A lightweight Python SDK for integrating Navimow robotic mowers with cloud platforms and smart home systems.

It provides a simple interface for device discovery, status monitoring, and mower control using REST APIs and MQTT-based real-time communication.

## Features

- REST API client for device management
- MQTT-based real-time status updates
- Device discovery
- Mower control (start, pause, resume, dock)
- Sync and async interfaces
- Designed for Home Assistant integrations

More features are being added over time.

## Installation

Install from PyPI:

```bash
pip install navimow-sdk
````

## Quick Example

```python
import aiohttp
from mower_sdk import MowerClient

client = MowerClient(
    session=aiohttp.ClientSession(),
    token="your_access_token",
    api_base_url="https://api.example.com",
    mqtt_broker="mqtt.example.com",
)

devices = await client.async_discover_devices()
print(devices)

await client.async_start_mowing("device_id")
```

> The SDK does not handle OAuth2 authentication. You must obtain the access token separately.

## Core Capabilities

* **Device Discovery** – Retrieve mower devices linked to an account
* **Device Status** – Get current mower state and battery level
* **Real-time Updates** – Receive MQTT status updates
* **Device Control** – Start, pause, resume mowing or return to dock

Typical mower states include:

* `idle`
* `mowing`
* `paused`
* `docked`
* `charging`
* `returning`
* `error`

## Contributing

Issues and Pull Requests are welcome.

## License

MIT License
