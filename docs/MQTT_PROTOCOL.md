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
- **MQTT Broker Host**: `thsprojuk.aliyun-hbbj-hisense.pubsub.tech` (Baidu Intelligent Cloud IoT Core / 百度智能云物联网核心套件，前端挂载阿里云 NLB 负载均衡)
- **Port**: `1883` (TCP) or `8883` (TLS / MQTTS)
- **Protocol**: MQTT v3.1.1 / v5.0 (supports standard `paho-mqtt` client)
- **Keepalive**: 60 seconds (`PINGREQ` / `PINGRESP`)

### 2.2 Client Credentials & Protocol Anatomy / 认证凭据结构与 ThingIDP 协议规范
Hisense smart home services utilize the **Baidu Intelligent Cloud IoT Core (百度智能云物联网套件) `thingidp` device identity protocol**:
- **Client ID**: Mobile client device ID (format: `aiotfffe<32_hex_chars>`).
  > **Important (Broker Anti-Collision Rule / 防互踢机制)**: MQTT brokers strictly enforce client ID uniqueness per broker instance. If two client instances connect using the identical Client ID simultaneously, the broker will drop the older connection immediately. Each independent client instance must utilize a distinct ID.
- **Username Template**:
  ```text
  {adp_type}@{IoTCoreId}|{DeviceKey}|{timestamp}|{algorithm_type}
  ```
  - `adp_type`: Fixed as `thingidp`.
  - `IoTCoreId`: The Hisense cloud IoT project suite ID: `thsprojuk`.
  - `DeviceKey`: Client Device Key (identical to Client ID: `aiotfffe<32_hex_chars>`).
  - `timestamp`: Timestamp in seconds (or fixed placeholder `0`).
  - `algorithm_type`: Hashing algorithm, fixed as `MD5`.
  - **Constructed Username**:
    ```text
    thingidp@thsprojuk|aiotfffe<32_HEX_CLIENT_DEVICE_ID>|0|MD5
    ```
- **Password Calculation Formula (MD5 Method)**:
  ```text
  password = MD5(f"{DeviceKey}&{timestamp}&{algorithm_type}{DeviceSecret}")
  ```
  For Hisense:
  ```text
  password = MD5(f"{DeviceKey}&0&MD5{DeviceSecret}").lower()
  ```
  *(Where `DeviceSecret` is the pre-registered secret issued by the IoT Core for this client device).*

### 2.3 Dynamic Configuration Endpoint / 云端动态配置接口
When the official mobile app starts, it issues an HTTP request to the push gateway to fetch broker credentials:
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

### 2.4 Multi-Client Isolation & Anti-Collision Strategies / 多客户端会话隔离与防互踢策略

To avoid MQTT broker session termination (mutual kicking) between Home Assistant and the official mobile app, the following three integration strategies are available:

1. **Path 1: Sub-Account Sharing (家庭子账号隔离机制 — 推荐普通用户，0 抓包)**:
   - **Operation**: In the official "海信爱家" app, navigate to **我的 -> 家庭管理 -> 成员管理 -> 添加成员** (or 共享设备), and invite a family member or secondary phone number.
   - **Integration Setup**: Sign into the Home Assistant integration using the secondary account credentials.
   - **Advantage**: The mobile phone uses Account A (`customerId_A`, `device_A`), while Home Assistant uses Account B (`customerId_B`, `device_B`). Both have full access to household appliances, maintain independent MQTT client sessions, and **never collide**. **Requires zero network sniffing (0 抓包)**.
   - 📖 **Detailed Guide / 详细教程**: See [Family Sub-Account Sharing Guide / 家庭副账号配置指引](SUB_ACCOUNT_GUIDE.md).
2. **Path 2: Dedicated Sniffed Credentials (专属设备凭据 — 适合极客用户)**:
   - **Operation**: Users sniff their own device's `deviceId` and `loginPassword` once via tools like Charles, Reqable, or Proxyman, and enter them into Home Assistant's configuration options.
   - **Advantage**: Bypasses the shared fallback pool with 100% dedicated broker credentials.
3. **Path 3: Gateway Dynamic Client Registration (动态网关注册逆向探索 — 正在推进中)**:
   - Technical research is underway to extract the signing secret for `appKey: "JHKAIHOME"` on `mqtt-msg.hismarttv.com` to dynamically register virtual device keys per HA instance automatically.

---

## 3. Topic Subscription Matrix / 主题订阅规范

To ensure zero dropped messages across multiple device categories, integrations **must subscribe to the full user wildcard topic** (`$iot/general/user/{customerId}/#`):

| Topic Pattern | Description | 说明 |
| :--- | :--- | :--- |
| `$iot/general/user/{customerId}/#` | **Mandatory** All downlink push messages for this user account across all apps and channels | **核心总线通道（必选）**：跨通道、跨品类接收全量推送 |
| `$iot/general/user/{customerId}/down/1123840823/8001008` | Appliance cycle complete push notifications (Washer complete, etc.) | 家电设备洗涤/烘干完成等核心业务推送 |
| `$iot/general/user/{customerId}/down/JHKAIHOME/#` | AIHome mobile app dedicated downlink channel | 爱家 App 专属业务下行通道 |
| `$iot/{clientDeviceId}/#` | Messages routed to this specific client session | 当前客户端专属通道 |
| `$iot/{applianceWifiId}/#` | Messages referencing physical appliance's WiFi ID | 物理设备 WiFi MAC/ID 专属推送通道 |
| `$iot/{applianceDeviceId}/#` | Messages referencing appliance Device ID | 物理设备 Device ID 专属推送通道 |
| `$iot/#` | Broker-level wildcard for all authorized IoT downlink messages | 云端所有已鉴权下行消息通配 |
| `#` | Global wildcard (supported by broker) | 全局通配符（Broker 确认支持） |

> ⚠️ **Critical Discovery / 避坑指南**:
> The official cloud pushes laundry completion notifications through channel **`1123840823`** (under tag `8001008`), **NOT** through `JHKAIHOME`! If an integration only subscribes to `$iot/.../down/JHKAIHOME/#`, cycle completion messages will be **completely missed**! Subscribing to `$iot/general/user/{customerId}/#` guarantees 100% message reception.

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

#### Pattern D: Cycle Completion & Notification Push (`msgContent`) / 洗涤完成与业务事件通知
Sent when a major lifecycle event completes (such as washing machine cycle complete):
```json
{
  "businessTag": "8001008",
  "channelApp": "1123840823",
  "dispatchAction": "0",
  "identifier": "msg",
  "messageId": "9cbb8780-e265-11f1-b844-3151eb0d2207_8001008_<CUSTOMER_ID>",
  "messageGeneratedTimeStamp": 1794737032585,
  "msgType": 2000,
  "msgTitle": "设备通知",
  "msgContent": "洗衣机已洗衣完毕，快去处理吧",
  "msgUsage": "userTask",
  "msgVersion": 1,
  "operationType": 28677,
  "pushType": 2,
  "targetCustomerId": "<CUSTOMER_ID>",
  "targetDeviceId": "aiotfffe<32_HEX_CLIENT_DEVICE_ID>",
  "text": "{\"msgContent\":\"洗衣机已洗衣完毕，快去处理吧\",\"msgTitle\":\"设备通知\",\"msgType\":2000}"
}
```
*Zero-Latency Handling*:
1. Display the human-readable notification text (`msgContent`) immediately on the entity's latest push sensor (`sensor.*_latest_push`).
2. When `businessTag == "8001008"` or `msgContent` indicates completion, immediately perform in-memory state transition (`run_status = 7` (complete), `remain_time = 0`, `start_pause_status = False`) without querying the cloud HTTP API!
3. Fire the `hisense_washer_complete` event on the Home Assistant event bus and issue a persistent notification.

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
| `detergentLackStatus` | string/int | `"0"`: Normal (充足), `"1"`: Empty/Lack (洗涤剂不足告警) | 洗涤剂耗材余量告警 |
| `softenLackStatus` | string/int | `"0"`: Normal (充足), `"1"`: Empty/Lack (柔顺剂不足告警) | 柔顺剂耗材余量告警 |
| `detergentMode` | int | Auto dispenser dosage level (`0`: Off, `1`: Normal, `2`: More, `3`: Less) | 洗涤剂自动投放挡位 |
| `softenMode` | int | Auto softener dosage level (`0`: Off, `1`: Normal, `2`: More, `3`: Less) | 柔顺剂自动投放挡位 |

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

---

## 7. App-Parity Architecture: Event Push & Local Countdown / 模拟官方 App 混合架构规范

Through comprehensive binary decompilation of the official Hisense AIHome APK (`libapp.so`), the underlying design of appliance synchronization was uncovered:

通过对海信爱家官方 APK 核心动态库（`libapp.so`）的深度反编译，揭示了官方 App 的状态同步底层架构机制：

### 7.1 Why Standby Power-On Has No MQTT Push / 为什么开机与运行中没有 MQTT 推送？
- **Discrete Notifications vs Telemetry Streams (通知与遥测分离)**:
  Hisense IoT cloud separates continuous appliance telemetry from user notifications. The appliance reports high-frequency protocol updates to the cloud backend over its internal device channel. The cloud backend **does not broadcast high-frequency state updates (power-on, per-minute timer countdowns) to the mobile client topic `$iot/general/user/{customerId}/#`**.
  海信 IoT 云端严格区分了“遥测数据流”与“通知消息”。洗衣机通过专有设备通道向云端上报高频数据，但云端**并不会把每一次开机、转速变化或分钟倒计时流向用户的 MQTT 通道**。
- **Official App Behavior (官方 App 处理方式)**:
  `LargeDevCardMultiWasherVM` does not implement `JhkMqttConsumer`. Instead, when the user opens the App card, it makes an on-demand HTTP query (`check_status`). If running, the App activates `_startTimeUpdateMode`, initiating a local countdown timer on the phone that ticks down remaining minutes locally, rather than streaming per-minute MQTT messages from the server.
  官方 App 洗衣机卡片没有实现 MQTT 消费者，而是在进入卡片时发起单次 HTTP 查询，一旦检测到运转，App 本地启动 `_startTimeUpdateMode` 自行进行分钟倒计时，而非依赖云端持续推流。

### 7.2 Home Assistant App-Parity Design / Home Assistant 拟真还原设计
To deliver an optimal user experience while strictly adhering to zero-ban safety rules:
为了在绝对保障 0 封号安全的前提下，提供与官方 App 相同的丝滑体验，集成采用以下三层拟真架构：

1. **Standby State: Zero Polling / 关机/待机：严格零轮询**:
   - `update_interval = None`: When idle, no HTTP requests are ever made. 100% immune to cloud frequency limits or IP blocks.
   - 待机与关机状态下完全不向云端发起任何轮询（0次请求），彻底杜绝封号隐患。
2. **Running State: Local Virtual Countdown / 运行中：本地分钟虚拟倒计时**:
   - When running state is confirmed (via HA manual refresh button, power plug automation, or cycle start), HA initializes `_start_app_countdown`.
   - Every 60 seconds, remaining minutes smoothly decrement in-memory and notify entity listeners, updating the UI smoothly with **0 network requests**.
   - 检测到开机运转时，自动启动本地虚拟倒计时，每 60 秒在内存中平滑扣减剩余时间并刷新实体，UI 实时倒计时，**产生 0 次云端网络请求**。
3. **Optional Dynamic Wash Polling (>= 5min Safe Rate) / 用户可选动态轮询（强制 >= 5分钟保底）**:
   - Users can configure whether to enable periodic cloud sync *during washing* in Integration Options (`enable_washer_dynamic_poll`).
   - **Hard Safety Limit**: Enforces a minimum interval of **at least 5 minutes** (`MIN_WASHER_POLL_INTERVAL = 5`). Even if enabled, a 30-minute wash cycle generates only ~6 requests, far below cloud anti-scraping thresholds.
   - 用户可在集成选项中自主选择是否在洗涤中开启定时校验。**强制硬编码轮询间隔不得小于 5 分钟**。即便开启，30 分钟洗涤仅请求 6 次，处于绝对安全的白名单频次内。
4. **Lifecycle Push Completion / 离散事件推送闭环**:
   - When the cycle completes, Hisense cloud pushes `businessTag: 8001008` (`"洗衣机已洗衣完毕，快去处理吧"`).
   - HA instantly catches this MQTT push, cancels the local countdown (`_stop_app_countdown`), resets entities to complete/idle, fires `hisense_washer_complete`, and sets `update_interval = None`.
   - 洗涤完成时云端下发 `8001008` 推送，HA 瞬间捕获，立即停止倒计时，重置实体状态为完成，并切断轮询恢复待机零请求。

