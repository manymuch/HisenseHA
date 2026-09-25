# Hisense Smart Devices (HisenseHA)
![Hisense](hisense-electronics.png)


[简体中文](README_zh-Hans.md)

Home Assistant custom integration for **Hisense** smart devices. It uses cloud APIs and currently supports air conditioners, washing machines, refrigerators.

## Requirements

- **Home Assistant** 2025.6 or newer (for older cores, see [releases](https://github.com/manymuch/HisenseHA/releases)).
- A **Hisense account** that can sign in to the official mobile app (same username and password).
- The AC, refrigerator, or supported washer must already be paired in the app and belong to a **home**.

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

## Status sync

This integration talks to the **Hisense AIHome cloud**. Device state is read during setup, after entity actions, and when you press **Force refresh**. There is no periodic polling. 

Each device exposes one **Diagnostic** button, **Force refresh**, which requests the current state once from the Hisense AIHome cloud. Each press causes a real cloud request; do not automate it as frequent polling.

If you need **real-time status update**, we recommend pairing the same Hisense device with **Mi Home** as well, then in Home Assistant use [Xiaomi Miot](https://github.com/al-one/hass-xiaomi-miot) or [Xiaomi Home](https://github.com/xiaomi/ha_xiaomi_home) to observe Mi Home state changes, and an **automation** that triggers this integration’s **Force refresh** button for the matching device when the Xiaomi entity changes, to sync Hisense entities indirectly.
