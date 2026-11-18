# 海信云端 MQTT 实时推送协议与多设备对接指南

本文档详细记录了海信爱家（Hisense AIHome）云端 MQTT 实时推送协议的技术实现细节、底层报文规范与架构机制。旨在为社区开发者与进阶用户提供权威参考，帮助大家无缝对接海信全品类智能设备（洗衣机、干衣机、空调、冰箱、洗碗机、蒸烤箱、电视等），构建零轮询、零封号、低延迟的稳定智能家居体系。

---

## 一、架构设计与核心原则

### 1.1 为什么必须采用 MQTT 推送（拒绝无脑轮询）？
海信云端开放接口（`api-cn.hismarttv.com` 等）部署了极其严苛的 WAF 防刷策略与风控限制。若在 Home Assistant 中采用传统的高频定时轮询（例如每 15~30 秒发起一次 HTTP 请求），每天将产生数千次访问，极易触发云端风控，导致**账号封禁或 IP 封锁**。

官方手机「海信爱家」App 在运行与后台常驻时，核心依赖 MQTT 长连接推送通道接收状态变化。在 Home Assistant 中复现这套 MQTT 通道，能够实现：
- **瞬时感知**：设备状态变化与洗涤结束秒级通知；
- **零请求风控**：待机与关机状态下 0 次主动查询，从源头杜绝封号。

```
+---------------------------+        +-----------------------------------+
|     海信智能家电设备      |        |        海信官方云端服务           |
|  (洗衣机 / 空调 / 冰箱)   |        |   (IoT 物联网后台 / 业务中心)     |
+-------------+-------------+        +-----------------+-----------------+
              |                                        |
              | 设备状态上报 (WiFi / 专有通道)          |
              +--------------------------------------->+
                                                       |
                                                       | 转发关键业务与状态推送
                                                       v
+---------------------------+        +-----------------+-----------------+
|      Home Assistant       |<-------+    百度智能云 / 阿里 IoT MQTT     |
|   (HisenseHA 自定义集成)  |  MQTT  |  (thsprojuk.aliyun...:1883)       |
+---------------------------+  推送  +-----------------------------------+
```

---

## 二、官方 App 状态同步真相与拟真机制

通过对海信官方爱家 App 核心动态库（`libapp.so`）进行深度逆向分析，我们发现了海信在智能家电状态同步上的真实底层逻辑：

### 2.1 为什么开机与运转中没有 MQTT 推送？
1. **遥测数据流与通知消息严格分离**：
   洗衣机等大型家电在运转中，其转速、水温、倒计时每秒都在变化。洗衣机通过底层专用通道向海信云端上报高频报文，但海信云端**绝不会把每一秒的遥测数据转发到用户的手机 MQTT 通道（`$iot/general/user/{customerId}/#`）**，否则会产生巨大的服务器推流带宽开销并消耗手机电量。
2. **官方 App 洗衣机卡片机制**：
   在官方 App 源码中，空调模块实现了 `JhkMqttConsumer`（接收温湿度推流），但洗衣机模块（`LargeDevCardMultiWasherVM`）**并未实现 MQTT 状态消费者**。
   官方 App 的真实做法是：
   - 用户打开 App 卡片时，通过 HTTP 接口查询一次当前状态；
   - 若检测到正在运转，App 本地启动 **`_startTimeUpdateMode`** 计时器，由手机自己在本地进行分钟平滑倒计时，而非依赖云端持续推流；
   - 洗涤结束时，由云端下发离散通知推送触发 `_stopTimerUpdateMode` 停止计时。
3. **MQTT 推送涵盖的业务范围**：
   海信云端仅在以下几个离散关键节点向用户下发推送：
   - **洗涤完成**：`businessTag: 8001008`，携带 `"msgContent": "洗衣机已洗衣完毕，快去处理吧"`；
   - **耗材告警**：柔顺剂不足、洗涤剂不足；
   - **异常报警**：门未关严、进水超时、排水异常；
   - **定期保养**：筒自洁保养提醒。

### 2.2 Home Assistant 拟真还原架构设计
基于上述机制，Home Assistant 实现了与官方 App 完全拟真的三层运行策略：

1. **关机与待机状态（严格零轮询）**：
   `update_interval = None`。设备关机或待机时，完全不向云端发起任何定时轮询（0 次请求），永远杜绝封号。
2. **洗涤运转状态（本地虚拟分钟倒计时）**：
   检测到洗衣机开机运转后（通过 HA 操作、刷新按钮或功率插座联动触发），自动启动本地异步倒计时协程。每 60 秒在内存中平滑扣减剩余分钟数并通知界面渲染，**产生 0 次云端网络请求**，提供与 App 相同的流畅倒计时体验。
3. **洗涤中动态同步（用户可选 · 强制 >= 5 分钟安全限制）**：
   用户可在集成选项中自主配置是否在洗衣运转中开启动态云端轮询。**系统强制硬编码轮询间隔不得小于 5 分钟**。即使开启，30 分钟的洗涤过程仅产生约 6 次请求，绝对处于海信风控安全阈值之内。
4. **离散事件推送闭环**：
   洗涤完成瞬间，海信云端下发 `8001008` 推送。Home Assistant 瞬间捕获该报文，立刻终止本地倒计时，将状态更新为完成，发出系统通知与总线事件，并自动将轮询重置为 `None` 恢复待机零请求。

---

## 三、MQTT 服务器连接与鉴权规范

### 3.1 服务器连接端点
- **服务器主机（Broker Host）**：`thsprojuk.aliyun-hbbj-hisense.pubsub.tech`（百度智能云物联网核心套件，前端配置阿里云负载均衡）
- **端口（Port）**：`1883`（标准 TCP 明文传输）或 `8883`（MQTTS / TLS 加密传输）
- **协议版本**：MQTT v3.1.1 / v5.0（标准 `paho-mqtt` 客户端直接支持）
- **心跳间隔（Keepalive）**：推荐 60 秒（定期收发 `PINGREQ` 与 `PINGRESP` 心跳）

### 3.2 客户端凭据结构与 ThingIDP 协议规范
海信智慧家采用**百度智能云物联网套件（Baidu IoT Core）`thingidp` 设备身份体系**：

#### 客户端 ID（Client ID）
- 格式：手机端设备标识，形如 `aiotfffe<32位十六进制字符>`。
> [!WARNING]
> **Broker 防互踢规则**：MQTT 协议强制要求同一 Broker 内 Client ID 必须全局唯一。若两个客户端使用完全相同的 Client ID 同时连入，服务器会立即掐断先连接的客户端。多端使用时必须保持会话隔离。

#### 用户名生成模板（Username Template）
```text
{adp_type}@{IoTCoreId}|{DeviceKey}|{timestamp}|{algorithm_type}
```
- `adp_type`：固定为 `thingidp`；
- `IoTCoreId`：海信云端 IoT 套件专属项目标识：`thsprojuk`；
- `DeviceKey`：客户端设备标识 Key（与 Client ID 一致：`aiotfffe<32位字符>`）；
- `timestamp`：时间戳占位符（可使用固定 `0`）；
- `algorithm_type`：签名摘要算法，固定为 `MD5`。
- **最终合成用户名格式**：
  ```text
  thingidp@thsprojuk|aiotfffe<32位设备ID>|0|MD5
  ```

#### 密码生成算法（Password Formula）
```text
password = MD5(f"{DeviceKey}&{timestamp}&{algorithm_type}{DeviceSecret}").lower()
```
代入海信固定参数：
```text
password = MD5(f"{DeviceKey}&0&MD5{DeviceSecret}").lower()
```
*（其中 `DeviceSecret` 为物联网套件为该设备注册时下发的通讯密钥，随设备绑定生成）。*

### 3.3 云端动态配置接口
官方手机 App 启动时，会通过 HTTP 网关动态换取最新的 MQTT 服务器与凭据配置：
- **请求地址**：`POST https://mqtt-msg.hismarttv.com/2.0/mqtt/config`
- **请求头（Headers）**：
  ```http
  Content-Type: application/json; charset=UTF-8
  User-Agent: JHKMain/7.0.8 (iPhone; iOS 27.0.1; Scale/3.00)
  X-Sign-For: <网关签名摘要>
  ```
- **请求体（JSON Body）**：
  ```json
  {
    "format": 1,
    "appKey": "JHKAIHOME",
    "deviceId": "aiotfffe<32位设备ID>",
    "clientType": 0,
    "timeStamp": 1794655797.269,
    "version": "2.0",
    "accessToken": "<用户访问令牌>",
    "languageId": 0
  }
  ```
- **云端响应示例**：
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
        "loginUserName": "thingidp@thsprojuk|aiotfffe<32位设备ID>|0|MD5",
        "loginPassword": "<32位MD5哈希密码>",
        "logReportTags": ["2001005"]
      },
      "status": "SUCCESS"
    }
  }
  ```

---

## 四、多客户端会话隔离与防互踢策略

为避免 Home Assistant 与官方手机 App 之间产生 MQTT 客户端抢占互踢，有以下三种落地方案：

### 方案 1：家庭子账号共享隔离（强烈推荐 · 0 抓包 · 零门槛）
- **操作步骤**：
  1. 在手机「海信爱家」App 中打开 **我的 -> 家庭管理 -> 成员管理 -> 添加成员**；
  2. 使用另一个备用手机号注册副账号并接受邀请，角色设为管理员；
  3. 为副账号设置好固定的账号密码，在 Home Assistant 中直接用副账号登录。
- **核心优势**：
  手机端运行在主账号（`Client_A`），Home Assistant 运行在副账号（`Client_B`）。两者在 Broker 上属于完全独立的两个长连接通道，**100% 互不干扰，永远不互踢，且完全不需要抓包**。
- 📖 **详细配置教程**：请参阅 [海信爱家家庭副账号共享配置指引](SUB_ACCOUNT_GUIDE.md)。

### 方案 2：提取专属设备抓包凭据（适合高阶玩家）
- 用户通过抓包工具（Reqable / Charles / Proxyman）抓取自己手机连接 `mqtt/config` 时的凭据，单独填入 Home Assistant。

### 方案 3：动态网关注册逆向模拟
- 通过本地模拟签名自动换取全新设备凭据，目前因官方签名包含混淆加固，推荐首选方案 1。

---

## 五、主题订阅矩阵与避坑指南

为确保不错过任何品类设备的推送，集成**必须订阅全量用户级通配主题**（`$iot/general/user/{customerId}/#`）：

| 主题模式（Topic Pattern） | 优先级 | 说明 |
| :--- | :--- | :--- |
| `$iot/general/user/{customerId}/#` | **核心必选** | **用户核心总线通配符**：跨应用、跨品类接收当前家庭的所有下行推送 |
| `$iot/general/user/{customerId}/down/1123840823/8001008` | 核心事件 | 洗衣机/干衣机洗涤完成等关键业务生命周期通知 |
| `$iot/general/user/{customerId}/down/JHKAIHOME/#` | 业务通道 | 爱家 App 专属业务通道（主要包含部分界面同步信息） |
| `$iot/{clientDeviceId}/#` | 客户端通道 | 指向当前连入客户端会话的专属消息 |
| `$iot/{applianceWifiId}/#` | 设备通道 | 指向物理家电 WiFi ID 的专属推送通道 |
| `$iot/{applianceDeviceId}/#` | 设备通道 | 指向物理家电 Device ID 的专属推送通道 |
| `$iot/#` | 调试全量 | 允许范围内的云端已鉴权消息通配 |
| `#` | 调试全量 | 全局通配符（Broker 鉴权规则内有效） |

> [!CAUTION]
> **重大避坑指南**：
> 海信云端的洗涤完成通知是通过通道 **`1123840823`**（业务标签 `8001008`）下发的，**而不是通过 `JHKAIHOME` 通道下发的**！
> 如果集成只订阅 `$iot/.../down/JHKAIHOME/#`，洗涤完成推送将被**完全漏掉**！必须订阅 `$iot/general/user/{customerId}/#` 才能确保 100% 接收全量业务事件。

---

## 六、报文格式与有效载荷解析

海信 MQTT 推送采用两层嵌套结构：外层为通用的 Envelope 封装，内层 `text` 字段包含具体的业务载荷 JSON 字符串。

### 6.1 外层封装报文结构
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
  "targetDeviceId": "aiotfffe<32位设备ID>",
  "text": "{\"action\":\"onDeviceStateUpdate\", ...}",
  "signatureServer": "..."
}
```

### 6.2 内层有效载荷解析（4 种核心模式）

#### 模式一：增量状态更新（`changeInfo`）
当设备的某个特定参数发生改变时触发（如用户旋转旋钮调速、开启童锁）：
```json
{
  "action": "onDeviceStateUpdate",
  "devId": "<设备ID>",
  "changeInfo": {
    "powerStatus": [1, 0],
    "runStatus": [4, 2],
    "remainRunTime": [35, 36],
    "dehydrationSpeed": [1400, 1200]
  }
}
```
*说明*：`changeInfo` 的数组格式为 `[新值, 旧值]`，便于直接增量更新实体。

#### 模式二：全量状态快照（`status`）
在运行程序发生重要阶段转换或设备首次上报时触发：
```json
{
  "action": "onDeviceStateUpdate",
  "devId": "<设备ID>",
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
*优化策略*：当报文中直接携带 `status` 字典时，直接在内存中更新实体状态，无需再次发起 HTTP 云端请求。

#### 模式三：家庭环境广播事件（`HomeStatusChanged`）
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

#### 模式四：业务生命周期与洗涤完成通知（`msgContent`）
洗衣机运行结束时由业务中心推送：
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
  "targetDeviceId": "aiotfffe<32位设备ID>",
  "text": "{\"msgContent\":\"洗衣机已洗衣完毕，快去处理吧\",\"msgTitle\":\"设备通知\",\"msgType\":2000}"
}
```
*零延迟处理链路*：
1. 直接提取 `msgContent` 文字，即时显示在「最新推送内容」实体上；
2. 当检测到业务标签为 `8001008` 或包含“洗衣完毕”时，立即在内存中切换 `run_status = 7`（完成），`remain_time = 0`，`is_running = False`；
3. 立即向 Home Assistant 事件总线派发 `hisense_washer_complete` 事件，并弹出持久化通知。

---

## 七、全品类家电设备字段与控制指令速查对照表

### 7.1 洗衣机与干衣机（核心字段与控制）
| 字段名称 | 类型 | 取值范围与含义 | 对应实体说明与控制指令 |
| :--- | :--- | :--- | :--- |
| `powerStatus` | string/int | `"1"`: 开机, `"0"`: 关机 | 电源开关实体（控制指令：`Power`） |
| `startPauseStatus` | string/int | `"0"`: 待机, `"1"`: 暂停, `"2"`: 运转中 | 运转/暂停状态 |
| `startStop` | string/int | `"1"`: 启动, `"0"`: 停止 | 启停开关实体（控制指令：`StartStop`） |
| `runStatus` | int | `0`: 待机<br>`1`: 预约等待<br>`2`: 主洗/称重<br>`3`: 漂洗<br>`4`: 脱水<br>`5`: 烘干<br>`7`: 完成<br>`10`: 抖散<br>`11`: 防皱 | 当前洗涤/烘干阶段枚举（`7` 触发完成通知） |
| `workMode` | int | 程序编号代码（如智能烘、棉麻、化纤、羊毛、单脱水等） | 程序选择实体（控制指令：`SetModes`） |
| `remainRunTime` | int | 剩余运转分钟数 | 剩余时间实体（支持本地平滑倒计时） |
| `washTemperature`| int | 水温（`0`: 冷水, `20`, `30`, `40`, `60`, `95` ℃） | 洗涤温度选择实体（控制指令：`SetTemperature`） |
| `dehydrationSpeed`| int | 转速（`0`: 不脱水, `400` ~ `1400` 转） | 脱水转速选择实体（控制指令：`SetSpin`） |
| `dryingMethod` | int | `0`: 关闭, `1`: 即穿, `2`: 即熨, `3`: 即存, `30`-`240`: 定时烘干（分） | 烘干模式选择实体 |
| `dryingModes` | int | `1`: 低温烘干, `0`: 标准烘干 | 低温烘干开关实体 |
| `doorLockStatus` | string/int | `"1"`: 已上锁, `"0"`: 未锁 | 门锁物理状态传感器 |
| `childLock` | string/int | `"1"`: 开启, `"0"`: 关闭 | 运转童锁开关实体（控制指令：`SetChildLock`） |
| `detergentLackStatus` | string/int | `"0"`: 充足, `"1"`: 耗尽不足 | 洗涤剂缺料告警传感器 |
| `softenLackStatus` | string/int | `"0"`: 充足, `"1"`: 耗尽不足 | 柔顺剂缺料告警传感器 |
| `detergentMode` | int | 自动投放量（`0`: 关闭, `1`: 标准, `2`: 多, `3`: 少） | 洗涤剂投放挡位实体 |
| `softenMode` | int | 柔顺剂投放量（`0`: 关闭, `1`: 标准, `2`: 多, `3`: 少） | 柔顺剂投放挡位实体 |

### 7.2 空调（核心字段与控制）
| 字段名称 | 类型 | 取值范围与含义 | 对应实体说明与控制指令 |
| :--- | :--- | :--- | :--- |
| `powerStatus` | string/int | `"1"`: 开机, `"0"`: 关机 | 空调温控器开关（控制指令：`Power`） |
| `modes` / `workMode` | int | `0`: 送风, `1`: 制热, `2`: 制冷, `3`: 除湿, `4`: 自动 | 运转模式（控制指令：`SetModes`） |
| `setTemperature` | float | 目标设定温度（16.0 ~ 32.0 ℃） | 设定温度（控制指令：`SetTemperature`） |
| `realTemperature`| float | 室内实测环境温度 | 当前室温传感器 |
| `humidity` / `realHumidity` | float | 室内实测湿度百分比 | 室内湿度传感器 |
| `windSpeed` | int | `1`: 微风, `2`: 低风, `3`: 中风, `4`: 高风 | 风速挡位（控制指令：`SetWindSpeed`） |
| `autoWind` | int/bool | `1`: 自动风速, `0`: 手动 | 自动风速控制（控制指令：`SetWindSpeed`） |
| `upDownWindFullControl` | int/bool | `1`: 开启上下摆风, `0`: 关闭 | 上下摆风开关（控制指令：`SetUpDownWindFullControl`） |
| `leftRightWindFullControl` | int/bool | `1`: 开启左右摆风, `0`: 关闭 | 左右摆风开关（控制指令：`SetLeftRightWindFullControl`） |
| `aiEcoSwitch` | int/bool | `1`: 开启AI节能, `0`: 关闭 | AI节能开关（控制指令：`SetAIEcoSwitch`） |
| `clearSwitch` | int/bool | `1`: 开启自清洁, `0`: 关闭 | 自清洁开关（控制指令：`SetClearSwitch`） |
| `prevDirectBlow` | int/bool | `1`: 开启防直吹, `0`: 关闭 | 防直吹开关（控制指令：`SetPrevDirectBlow`） |
| `screenSwitch` | int/bool | `1`: 开启屏显, `0`: 关闭屏显 | 屏显开关（控制指令：`SetScreenSwitch`） |
| `heatSwitch` | int/bool | `1`: 开启电辅热, `0`: 关闭 | 电辅热开关（控制指令：`SetHeatSwitch`） |
| `fastCoolHeatSwitch` | int/bool | `1`: 开启强力冷热, `0`: 关闭 | 快速冷暖开关（控制指令：`SetFastCoolHeatSwitch`） |

### 7.3 冰箱（核心字段与控制）
| 字段名称 | 类型 | 取值范围与含义 | 对应实体说明与控制指令 |
| :--- | :--- | :--- | :--- |
| `refrigeratorSetTemperature` | int | 冷藏室设定温度（2 ~ 8 ℃） | 冷藏室目标温度（控制指令：`SetTemperature.Refrigerator`） |
| `freezeSetTemperature` | int | 冷冻室设定温度（-25 ~ -15 ℃） | 冷冻室目标温度（控制指令：`SetTemperature.Freeze`） |
| `refrigeratorRealTemperature`| int | 冷藏室实测温度 | 冷藏室实时温度传感器 |
| `freezeRealTemperature` | int | 冷冻室实测温度 | 冷冻室实时温度传感器 |
| `dBDDegerming` | string/int | `"1"`: 运行中, `"0"`: 停止 | 离子除菌+净味开关（控制指令：`DBDDegerming`） |
| `ionFreshSwitch` | string/int | `"1"`: 开启离子保鲜, `"0"`: 关闭 | 离子净味保鲜开关（控制指令：`SetIonFreshSwitch`） |
| `variationTemperatureSwitch` | string/int | `"1"`: 变温室开启, `"0"`: 关闭 | 变温室启闭开关（控制指令：`SetVariationTemperatureSwitch`） |
| `variationTempSpaceDrawer` | int | `0`: 原鲜/冰鲜, `1`: 0℃养鲜/零度, `2`: 母婴 | 变温抽屉模式选择实体 |
| `workMode.Smart` | string/int | `"1"`: 智能模式开启, `"0"`: 关闭 | 智能模式开关（控制指令：`SetModes.Smart`） |
| `workMode.QuickCooling` | string/int | `"1"`: 速冷模式开启, `"0"`: 关闭 | 速冷模式开关（控制指令：`SetModes.QuickCooling`） |
| `workMode.SuperFrozen` | string/int | `"1"`: 急冻模式开启, `"0"`: 关闭 | 急冻模式开关（控制指令：`SetModes.SuperFrozen`） |
| `workMode.Holiday` | string/int | `"1"`: 假日模式开启, `"0"`: 关闭 | 假日模式开关（控制指令：`SetModes.Holiday`） |
| `workMode.Daily` | string/int | `"1"`: 日常模式开启, `"0"`: 关闭 | 日常模式开关（控制指令：`SetModes.Daily`） |
| `workMode.KeepFresh` | string/int | `"1"`: 保鲜模式开启, `"0"`: 关闭 | 保鲜模式开关（控制指令：`SetModes.KeepFresh`） |
| `workMode.Party` | string/int | `"1"`: 聚会模式开启, `"0"`: 关闭 | 聚会模式开关（控制指令：`SetModes.Party`） |
| `workMode.PowerSaving` | string/int | `"1"`: 节能模式开启, `"0"`: 关闭 | 节能模式开关（控制指令：`SetModes.PowerSaving`） |
| `aiEcoSwitch` | string/int | `"1"`: AI节能开启, `"0"`: 关闭 | 冰箱AI节能开关（控制指令：`SetAIEcoSwitch`） |
| `refriOpenDoorAlarm` | string/int | `"1"`: 门未关好告警, `"0"`: 正常 | 冷藏门开告警传感器 |
| `freezeOpenDoorAlarm` | string/int | `"1"`: 门未关好告警, `"0"`: 正常 | 冷冻门开告警传感器 |

### 7.4 电视（核心字段、媒体控制与按键事件）
| 字段名称 / 按键码 | 类型 | 取值范围与含义 | 对应实体说明与控制指令 |
| :--- | :--- | :--- | :--- |
| `powerStatus` | string/int | `"1"`: 开机, `"0"`: 关机 | 媒体播放器开关（控制指令：`Power` / `KEY_POWER`） |
| `volume` | int | 0 ~ 100 电视音量 | 媒体播放器音量（控制指令：`KEY_VOLUMEUP`, `KEY_VOLUMEDOWN`） |
| `mute` | bool | `true`: 静音, `false`: 正常 | 媒体播放器静音开关（控制指令：`KEY_MUTE`） |
| `source` | string | 当前信号源通道 | 信号源传感器 |
| `KEY_HOME` | 按键码 | 主页键 | 遥控按键实体（主页） |
| `KEY_RETURNS` | 按键码 | 返回键 | 遥控按键实体（返回） |
| `KEY_MENU` | 按键码 | 菜单键 | 遥控按键实体（菜单） |
| `KEY_OK` | 按键码 | 确认键 | 遥控按键实体（确认） |
| `KEY_UP` / `DOWN` / `LEFT` / `RIGHT` | 按键码 | 方向上下左右导航键 | 遥控按键实体（方向导航） |
| `KEY_CONTROL_CENTER` | 按键码 | 控制中心快捷键 | 遥控按键实体（控制中心） |
> [!NOTE]
> **电视双通道控制架构**：
> 1. **云端通道**：通过海信云端动作网关下发 `connector.device.command.PressKeyEvent` 与推送接口 `https://mobile-aiot.hismarttv.com/mobilemsg/push/v5.3/remoter`；
> 2. **局域网通道**：通过本地 UPnP `LanControlInfo` 协议（服务标识 `urn:schemas-upnp-org:service-1-0`）发送 `OpClass` / `OpType` / `OpPara` 实现极低延迟本地遥控。

### 7.5 洗碗机与蒸烤箱
- **洗碗机**：`runStatus` 状态映射为 `0: 待机, 1: 预洗, 2: 主洗, 3: 漂洗, 4: 烘干, 7: 完成`。
- **蒸烤箱**：`workMode` 对应各烹饪模式；`targetTemp` 与 `remainRunTime` 分别表示设定温度与剩余烘烤时间。

---

## 八、Home Assistant 开发者最佳实践

1. **坚持待机 0 轮询（`update_interval = None`）**：
   家电设备在闲置、关机或待机时，切勿配置定时周期轮询。完全依托 MQTT 推送驱动，杜绝被海信云端封号的隐患。
2. **跨线程安全派发（Thread-Safe Dispatch）**：
   Paho MQTT 回调运行于后台线程中，所有状态变更必须安全派发至 Home Assistant 的主事件循环：
   ```python
   loop.call_soon_threadsafe(callback, device_id, message_data)
   ```
3. **快照优先直接更新（Skip Redundant HTTP）**：
   若推送数据直接携带了 `status` 字典，直接在内存中更新实体属性并刷新侦听器，避免发起二次 HTTP 查询。
4. **广播标准化总线事件（Event-Driven Automation）**：
   收到推送时在事件总线上派发 `hisense_mqtt_message`，洗涤结束时派发 `hisense_washer_complete`，极大方便用户通过自动化联动小爱音箱播报或手机推送信鸽。
5. **洗涤中轮询强制风控保底（>= 5 分钟限制）**：
   若提供运行中动态轮询选项，必须在配置流与后台调度器中双重锁定最低时间阈值（不得小于 5 分钟），保护用户账号安全。
