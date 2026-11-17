# Hisense Cloud MQTT Push Protocol & Integration Guide
# 海信云端 MQTT 实时推送协议与多设备对接指南

This document provides a comprehensive technical reference for the MQTT push protocol used by the Hisense AIHome cloud (海信爱家). It is intended to help developers integrate additional Hisense devices (Air Conditioners, Refrigerators, Dishwashers, Ovens, TV, etc.) into Home Assistant without relying on periodic polling.

本文档详细记录了海信爱家（Hisense AIHome）云端 MQTT 实时推送协议的技术实现细节与报文规范，旨在为社区开发者提供参考，帮助大家无缝对接海信全品类智能设备（空调、冰箱、洗碗机、蒸烤箱、电视等），实现零轮询、防封号的纯实时推送集成。

---

## 1. Architecture Overview / 架构概述

### Why MQTT Push (Zero-Polling)? / 为什么必须使用 MQTT 推送（零轮询架构）？
Hisense cloud APIs (`api-cn.hismarttv.com`) implement strict request throttling and anti-abuse policies. Repeated periodic HTTP polling (e.g. every 15–30 seconds) can trigger cloud account suspensions or IP bans. The official mobile app (海信爱家) relies on a persistent MQTT connection for instant status updates. By replicating this MQTT long connection, Home Assistant achieves instant status updates and cycle notifications with **zero background polling**.

海信云端 API 具有严格的请求频次限制与风控策略。周期性定时轮询（如 15~30 秒一次）极易触发云端封号或限制访问。官方“海信爱家”App 在手机前台运行时，完全依托 MQTT 长连接通道接收设备状态推送。通过在 Home Assistant 中复现这一 MQTT 长连接，不仅能做到设备开机、关机、运行阶段突变时秒级感知，还彻底消除了主动轮询导致的封号风险。

```
+---------------------------+        +-----------------------------------+
|  Hisense Appliance        |        |  Hisense Cloud Services           |
|  (Washer / AC / Fridge)   |        |  (IoT / AIHome Backend)           |
+-------------+-------------+        +-----------------+-----------------+
              |                                        |
              | Device status report via WiFi           |
              +--------------------------------------->+
                                                       |
                                                       | Forward state update
                                                       v
+---------------------------+        +-----------------+-----------------+
|  Home Assistant           |<-------+  Alibaba Cloud IoT MQTT Broker    |
|  (HisenseHA Integration)  |  MQTT  |  (thsprojuk.aliyun...:1883)       |
+---------------------------+  Push  +-----------------------------------+
```

---

## 2. Broker Connection & Authentication / 连接与鉴权

### 2.1 Connection Endpoints / 服务器端点
- **MQTT Broker Host**: `thsprojuk.aliyun-hbbj-hisense.pubsub.tech` (Alibaba Cloud IoT / EMAS)
- **Port**: `1883` (TCP) or `8883` (TLS / MQTTS)
- **Protocol**: MQTT v3.1.1 / v5.0 (supports standard `paho-mqtt` client)
- **Keepalive**: 60 seconds (`PINGREQ` / `PINGRESP`)

### 2.2 Client Credentials / 认证凭据结构
Hisense uses Alibaba Cloud IoT Device authentication:
- **Client ID**: Mobile client device ID (format: `aiotfffe<mac_or_uuid>`).
  > **Important**: MQTT brokers strictly enforce client ID uniqueness. If two clients connect using the identical Client ID simultaneously, the broker disconnects the previous connection. Ensure each client instance uses a unique ID.
- **Username**:
  ```text
  thingidp@thsprojuk|<client_device_id>|0|MD5
  ```
- **Password**: Cloud-issued MD5 token corresponding to the client device ID.

### 2.3 Dynamic Configuration Endpoint / 云端动态配置接口
The app periodically fetches broker credentials and registers device online status:
- **URL**: `POST https://mqtt-msg.hismarttv.com/2.0/mqtt/config`
- **Headers**:
  ```http
  Content-Type: application/json; charset=UTF-8
  User-Agent: JHKMain/7.0.8 (iPhone; iOS 27.0.1; Scale/3.00)
  X-Sign-For: <Base64_MD5_Gateway_Signature>
  ```
- **Request Body**:
  ```json
  {
    "format": 1,
    "appKey": "JHKAIHOME",
    "deviceId": "aiotfffe<32_HEX_CLIENT_DEVICE_ID>",
    "clientType": 0,
    "timeStamp": 1794655797.269,
    "version": "2.0",
    "accessToken": "<YOUR_ACCESS_TOKEN>",
    "languageId": 0
  }
  ```
- **Response**:
  ```json
  {
    "response": {
      "code": 0,
      "info": {
        "channelEnable": "2",
        "connectUrl": "tcp://thsprojuk.aliyun-hbbj-hisense.pubsub.tech:1883",
        "version": "4.0",
        "pubTopic": "$iot/deviceId/user/up/9/JHKAIHOME/3/1601001",
        "pubTopicIm": "$iot/deviceId/user/up/9/JHKAIHOME/3/1601002",
        "deviceIdSubTopic": "$iot/deviceId/user/down/JHKAIHOME/#",
        "userSubTopic": "$iot/general/user/customerId/down/JHKAIHOME/#",
        "loginUserName": "thingidp@thsprojuk|aiotfffe<32_HEX_CLIENT_DEVICE_ID>|0|MD5",
        "loginPassword": "<MD5_PASSWORD_HASH>",
        "logReportTags": ["2001005"]
      },
      "status": "SUCCESS"
    }
  }
  ```

---

## 3. Topic Subscription Matrix / 主题订阅规范

To ensure zero dropped messages across multiple device categories, integrations should subscribe to the following hierarchy:

| Topic Pattern | Description | 说明 |
| :--- | :--- | :--- |
| `$iot/general/user/{customerId}/#` | All downlink push messages for the user account | 用户全量下行总线通道（跨家庭、跨设备） |
| `$iot/general/user/{customerId}/down/JHKAIHOME/#` | Downlink push messages for AIHome app | 爱家 App 专属业务下行通道 |
| `$iot/{clientDeviceId}/#` | Messages routed to this client session | 当前客户端专属通道 |
| `$iot/{applianceWifiId}/#` | Messages referencing physical appliance's WiFi ID | 物理设备 WiFi MAC/ID 专属推送通道 |
| `$iot/{applianceDeviceId}/#` | Messages referencing appliance Device ID | 物理设备 Device ID 专属推送通道 |
| `$iot/#` | Broker-level wildcard for all authorized IoT downlink messages | 云端所有已鉴权下行消息通配 |
| `#` | Global wildcard (supported by broker) | 全局通配符（Broker 确认支持） |

---

## 4. Message Envelopes & Payload Schema / 推送报文规范

All Hisense MQTT messages arrive as a JSON envelope containing metadata and an inner payload.

### 4.1 Outer Envelope Structure / 外层封装报文
```json
{
  "businessTag": "JHkDeviceChangeBizMessage",
  "channelApp": "JHKAIHOME",
  "dispatchAction": "0",
  "identifier": "msg",
  "messageId": "06dc3a60-e0b3-11f1-8b2f-ff7d8f12241a_91222600_<CUSTOMER_ID>",
  "messageGeneratedTimeStamp": 1794719494821,
  "msgUsage": "subscribeReminder",
  "msgVersion": 1,
  "pushType": 2,
  "targetCustomerId": "<CUSTOMER_ID>",
  "targetDeviceId": "aiotfffe<32_HEX_CLIENT_DEVICE_ID>",
  "text": "{\"action\":\"onDeviceStateUpdate\", ...}",
  "signatureServer": "..."
}
```

### 4.2 Inner Payload Types (`text` field) / 内层有效载荷

#### Pattern A: Incremental State Change (`changeInfo`) / 增量状态更新
Sent when specific attributes change (e.g. power toggled, speed adjusted):
```json
{
  "action": "onDeviceStateUpdate",
  "devId": "<APPLIANCE_DEVICE_ID>",
  "changeInfo": {
    "powerStatus": [1, 0],
    "runStatus": [4, 2],
    "remainRunTime": [35, 36],
    "dehydrationSpeed": [1400, 1200]
  }
}
```
*Note*: `changeInfo` arrays provide `[new_value, old_value]`.

#### Pattern B: Full State Dictionary Snapshot (`status`) / 全量状态快照
Sent upon significant program transitions or initial status broadcast:
```json
{
  "action": "onDeviceStateUpdate",
  "devId": "<APPLIANCE_DEVICE_ID>",
  "status": {
    "powerStatus": "1",
    "runStatus": "4",
    "startPauseStatus": "2",
    "startStop": "1",
    "workMode": "2",
    "remainRunTime": "35",
    "washTemperature": "30",
    "dehydrationSpeed": "1400",
    "detergentMode": "1",
    "softenMode": "5",
    "childLock": "0",
    "doorLockStatus": "1"
  }
}
```
*Optimization*: When `status` is present, update the integration's memory state directly via `_update_from_states(status)` without querying the HTTP API!

#### Pattern C: Environmental / Home-Wide Notifications / 家庭环境事件广播
```json
{
  "action": "HomeStatusChanged",
  "homeId": "91222600",
  "states": [
    {"code": "temperature", "value": "24.5"},
    {"code": "humidity", "value": "55"}
  ]
}
```
*Handling*: When payload contains an event trigger without a full state dictionary, schedule a single on-demand cloud refresh (`coord.async_start_refresh()`).

---

## 5. Device Attribute Mapping Reference / 设备字段速查与对接指南

### 5.1 Washing Machines & Dryers / 洗衣机与干衣机
| Field | Type | Values & Meanings | 说明 |
| :--- | :--- | :--- | :--- |
| `powerStatus` | string/int | `"1"`: On, `"0"`: Off | 电源开关状态 |
| `startPauseStatus` | string/int | `"0"`: Standby, `"1"`: Paused, `"2"`: Running | 运行/暂停核心标志位 |
| `startStop` | string/int | `"1"`: Start, `"0"`: Stop | 启停状态 |
| `runStatus` | int | `0`: 待机 (Standby)<br>`1`: 预约等待 (Reservation)<br>`2`: 主洗/称重 (Main wash)<br>`3`: 漂洗 (Rinse)<br>`4`: 脱水 (Spin)<br>`5`: 烘干 (Drying)<br>`7`: 洗涤完成 (Complete)<br>`10`: 抖散 (Air dry)<br>`11`: 防皱 (Fresh care) | 当前洗涤阶段枚举 |
| `workMode` | int | Program code (`2`: 混合, `35`: 单烘, `22`: AI智洗, etc.) | 洗涤程序代码 |
| `remainRunTime` | int | Remaining minutes | 剩余运转分钟数 |
| `washTemperature`| int | Water temp in °C (`0`: Cold, `20`, `30`, `40`, `60`, `95`) | 洗涤水温 |
| `dehydrationSpeed`| int | Spin speed RPM (`0`: No spin, `400` ~ `1400`) | 脱水转速 |
| `dryingMethod` | int | `0`: Off, `1`: Extra Dry (即穿), `2`: Iron Dry (即熨), `3`: Cupboard Dry (即存), `30`-`240`: Timed Dry (min) | 烘干模式与定时 |
| `dryingModes` | int | `1`: Low-temperature softbaking (低温烘), `0`: Standard | 低温烘干开关 |
| `doorLockStatus` | string/int | `"1"`: Locked, `"0"`: Unlocked | 门锁物理状态 |
| `childLock` | string/int | `"1"`: Locked, `"0"`: Unlocked (Only settable when machine is running) | 童锁状态 |

### 5.2 Air Conditioners / 空调
| Field | Type | Values & Meanings | 说明 |
| :--- | :--- | :--- | :--- |
| `powerStatus` | string/int | `"1"`: On, `"0"`: Off | 开机/关机 |
| `workMode` | int | `0`: Cool (制冷), `1`: Dry (除湿), `2`: Fan (送风), `3`: Heat (制热), `4`: Auto (智能) | 运转模式 |
| `setTemp` | float | Target temperature (°C, 16.0 ~ 32.0) | 设定温度 |
| `windSpeed` | int | `0`: Auto, `1`: Low, `2`: Medium, `3`: High, `4`: Turbo | 风速档位 |
| `indoorTemp` | float | Current ambient room temperature | 室内实测温度 |

### 5.3 Refrigerators / 冰箱
| Field | Type | Values & Meanings | 说明 |
| :--- | :--- | :--- | :--- |
| `coldClosetTemp` | int | Cold compartment set temperature (°C, 2 ~ 8) | 冷藏室设定温度 |
| `freezeClosetTemp`| int | Freezer set temperature (°C, -24 ~ -15) | 冷冻室设定温度 |
| `refrigeratorRealTemperature` | int | Real-time sensor temperature | 实时温区温度 |
| `superCool` | int | `1`: Fast cooling active | 速冷模式 |
| `superFreeze` | int | `1`: Fast freezing active | 急冻模式 |
| `degerming` | int | `1`: Plasma sterilization active | 净味除菌开关 |
| `doorOpenStatus` | int | `1`: Door left open warning | 门未关严警报 |

### 5.4 Dishwashers & Ovens / 洗碗机与蒸烤箱
- **Dishwashers (洗碗机)**: `runStatus` 映射为 `0: 待机, 1: 预洗, 2: 主洗, 3: 漂洗, 4: 烘干, 7: 完成`。
- **Ovens/Steamers (蒸烤箱)**: `workMode` 表示烘烤/纯蒸模式；`targetTemp` 与 `remainRunTime` 表示设定温度与剩余时间。

---

## 6. Implementation Best Practices for Home Assistant / 集成开发最佳实践

1. **Keep `update_interval = None` (保持零轮询)**:
   Never configure regular polling on device update coordinators for appliances. Let MQTT handle state propagation to protect user accounts from being blocked.
   切勿为家电设备的 Coordinator 配置定时周期轮询。完全由 MQTT 推送驱动，杜绝高频请求封号风险。
2. **Handle Threading Safely (主事件循环安全调度)**:
   The Paho MQTT client callbacks run on a background thread. Always dispatch updates to Home Assistant's event loop:
   ```python
   loop.call_soon_threadsafe(callback, device_id, message_data)
   ```
3. **Parse Direct State Snapshots (`raw_states`) (直接解析全量状态快照)**:
   If incoming MQTT messages include `status` dictionaries, update device attributes in-memory directly without triggering any HTTP round-trip.
   推送携带 `status` 字段时，直接在内存中解析并触发实体更新，无需再向云端发请求。
4. **Coalesce Downstream Refreshes (合并防抖刷新)**:
   When receiving general events (e.g. `HomeStatusChanged`), coalesce refreshes with debouncing so multiple simultaneous messages don't generate redundant HTTP queries.
5. **Fire Home Assistant Events (广播标准化系统总线事件)**:
   Fire `hisense_mqtt_message` on the event bus for all incoming payloads to allow user automations, and `hisense_washer_complete` when cycles finish.
   收到推送时在 HA 事件总线上广播 `hisense_mqtt_message`，洗涤完成时触发 `hisense_washer_complete`，极大方便用户编写自动化联动。
