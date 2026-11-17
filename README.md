# Hisense Smart Devices (HisenseHA)
![Hisense](hisense-electronics.png)


[简体中文](README_zh-Hans.md)

Home Assistant custom integration for **Hisense** smart devices. It uses cloud APIs and currently supports air conditioners, washing machines, dryers, refrigerators.

## Requirements

- **Home Assistant** 2025.6 or newer (for older cores, see [releases](https://github.com/manymuch/HisenseHA/releases)).
- A **Hisense account** that can sign in to the official mobile app (same username and password).
- The AC, refrigerator, or supported washer/dryer must already be paired in the app and belong to a **home**.

## Install the integration

### Option A: HACS

[![Open your Home Assistant instance and add this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=manymuch&repository=HisenseHA&category=integration)

Click the button above, or manually:

1. Open **HACS** in Home Assistant.
2. Go to **Integrations** → menu (⋮) → **Custom repositories**.
3. Add repository `https://github.com/manymuch/HisenseHA`, category **Integration**.
4. On the **Hisense Smart Devices** card, click **Download**.
5. **Restart** Home Assistant when prompted.

### Option B: Manual install

1. Download a release archive from [Releases](https://github.com/manymuch/HisenseHA/releases), extract it, and copy the contents into your Home Assistant configuration directory:

   `config/custom_components/hisense/`

2. **Restart** Home Assistant.

## Add devices

1. Go to **Settings** → **Devices & services** → **Add integration**.
2. Search for **Hisense Smart Devices** (or **Hisense**) and select it.
3. Enter your **Hisense app username and password** (wrong credentials will show an authentication error).
4. Choose the **home** that contains your device.
5. Select one or more **devices**, then finish the wizard.

## Status Sync & Real-time Push Notifications

This integration communicates with the **Hisense AIHome cloud** and features built-in **MQTT push notification listening**:
1. **Real-time Push**: The integration maintains a long-lived MQTT connection with the Hisense push server, receiving real-time status updates and cycle completion events.
   - When wash cycle completion is detected, a persistent notification is created in Home Assistant, and a `hisense_washer_complete` event is fired on the event bus for easy automation (e.g. mobile push or smart speaker announcement).
   - Any incoming device push triggers the `hisense_mqtt_message` event.
2. **On-demand Refresh**: Device state is also updated after entity actions or when pressing the **Force refresh** diagnostic button.

> 💡 **Developer Reference**: For in-depth technical specifications of the Hisense cloud MQTT broker, authentication mechanisms, topic hierarchies, and payload schemas across appliances (Washer, Dryer, AC, Refrigerator, Dishwasher, Oven), please see the [Hisense Cloud MQTT Push Protocol & Integration Guide](docs/MQTT_PROTOCOL.md).

## Features

- **Air Conditioner**: Power, HVAC modes (cool/heat/fan/dry), target temperature, fan speed.
- **Refrigerator**: Compartment temperatures, super freeze/cool modes, sterilization switch, smart noise reduction.
- **Washing Machine** (Full bidirectional monitoring and control):
  - **Switches**: Power, Start/Pause, Running Child Lock.
  - **Program Selection**: 37 washer programs (Mixed, Single Dry, AI Wash & Dry, Down, Wool, Quick, Air Wash, etc.).
  - **Dispenser Control**: Auto-detergent and softener dosage presets.
  - **Cycle Settings**: Wash water temperature, wash duration, rinse frequency, spin speed (with automatic firmware safety interlocking during drying).
  - **Drying Modes**: Ready-to-wear, ironing, storage, timed dry (30m to 4h), and low-temperature drying (Softbaking).
- **Dryer**: State, remaining time, dry level and temperature monitoring.
