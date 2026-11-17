# Hisense AIHome Family Sub-Account Sharing Guide (Zero-Sniffing & Anti-Collision)
# 海信爱家家庭副账号共享配置指引（0 抓包 · 彻底防互踢 · 零门槛）

This guide explains how to use Hisense's official **Family Sharing** feature to connect Home Assistant using a secondary account. This provides dedicated, collision-free MQTT push notifications without requiring any network packet sniffing.

本指引详细介绍如何通过「海信爱家」官方的**家庭成员共享功能**，为 Home Assistant 配置专属的家庭副账号。该方案**无需任何抓包工具**（0 抓包、0 门槛），即可彻底杜绝手机 App 与 Home Assistant 之间的 MQTT 客户端会话抢占互踢，实现 100% 稳定的实时状态与洗涤完成推送。

---

## 1. Why Use a Sub-Account? / 为什么要使用家庭副账号？

### The Broker Collision Problem / 核心痛点：单账号抢占互踢
* Hisense AIHome uses Alibaba Cloud / Baidu IoT Core MQTT brokers for real-time notifications.
* When Home Assistant connects to the MQTT broker using the same account credentials as your mobile phone, the broker detects identical Client IDs / user sessions.
* According to standard MQTT broker rules, **the older connection is immediately dropped** ("mutual kicking" / 互踢). This causes:
  * Frequent push disconnects on Home Assistant;
  * The mobile app prompting "Logged in from another device" or losing real-time updates.

### The Sub-Account Solution / 官方家庭共享方案优势
* **0 抓包 (Zero Packet Sniffing)**: You do not need Charles, Reqable, Proxyman, or Wireshark. Setup takes 1 minute in the official app UI.
* **Complete Session Isolation (完全独立的会话)**: Your mobile phone runs under **Account A**, while Home Assistant runs under **Account B**. Both maintain independent, non-conflicting MQTT connections simultaneously.
* **Full Device Access (全量家电设备互通)**: Through Hisense's cloud home-sharing mechanism, Account B has full control and sensor monitoring access to all devices (washer, dryer, AC, refrigerator, etc.) in the home.
* **Permanent Stability (永久稳定)**: Sub-account credentials never expire and are immune to app foreground/background switching.

---

## 2. Step-by-Step Configuration / 详细操作配置步骤

```
+-------------------------------------------------------------+
|                      海信爱家云端家庭                        |
|                     (Home: "我的家")                        |
+------------------------------+------------------------------+
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
+-----------------------+             +-----------------------+
|      主账号 (用户手机)  |             |     副账号 (HA 专属)   |
|   (Phone: 138xxxx1111)|             |   (Phone: 139xxxx2222)|
|   登录官方手机 App     |             |   登录 Home Assistant |
|   拥有家庭所有权       |             |   角色: 管理员 / 成员  |
+-----------------------+             +-----------------------+
            |                                     |
    MQTT Client ID A                      MQTT Client ID B
  (独立连接，永不冲突)                  (独立连接，永不冲突)
```

### 第一步：准备或注册一个副账号 (Step 1: Prepare a Secondary Account)
1. 准备一个副手机号（可以使用家人的手机号，或您个人的副卡、备用手机号）。
2. 在「海信爱家」App 登录界面选择该手机号进行注册或登录。
3. **重要：设置固定登录密码**：
   * 许多用户平时习惯使用短信验证码登录，**但 Home Assistant 接入需要账号密码**。
   * 打开「海信爱家」App，进入 **我的 -> 设置（右上角齿轮）-> 账号与安全 -> 修改密码 / 设置密码**，为该副账号设置一个固定的登录密码。

---

### 第二步：在主账号中添加家庭成员 (Step 2: Invite the Secondary Account)
1. 在手机上登录您绑定了洗衣机/空调/冰箱的**主账号**。
2. 点击底部导航栏 **「我的」**。
3. 找到并点击 **「家庭管理」**（部分版本显示为「我的家庭」）。
4. 点击包含智能家电的目标家庭（例如默认的“我的家”）。
5. 点击 **「成员管理」** -> **「添加成员」**（或「邀请成员」）。
6. 输入**副账号的手机号**：
   * 成员角色建议选择 **「管理员」**（拥有所有设备的完整控制权与联动权限）。
7. 点击发送邀请。

---

### 第三步：副账号接受邀请与确认 (Step 3: Accept Invitation & Verify)
1. 在副账号手机（或在 App 退出主账号临时登录副账号）上查看通知。
2. 接受家庭加入邀请。
3. 确认副账号的 App 首页中能正常看到家庭内绑定的所有家电设备（如洗衣机、空调、冰箱等），并且能够正常查看状态。

---

### 第四步：在 Home Assistant 中配置集成 (Step 4: Configure HisenseHA)
1. 打开您的 Home Assistant 控制台。
2. 进入 **设置 -> 设备与服务 -> 添加集成**。
3. 搜索并选择 **Hisense Smart Devices (海信智能设备)**。
4. 在配置弹窗中：
   * **用户名 (Username)**：输入**副账号的手机号**。
   * **密码 (Password)**：输入在第一步中为副账号设置的**固定登录密码**。
5. 点击提交后，选择目标家庭（如“我的家”），勾选需要接入的设备，完成配置向导。

---

## 3. Verification & Results / 效果验证

完成上述配置后：
1. **状态即时同步**：洗衣机开机、关机、切换洗涤程序、调整水温转速时，Home Assistant 秒级更新。
2. **洗完即时提醒**：洗衣程序结束时，HA 零延迟接收 `$iot/general/user/{customerId}/down/1123840823/8001008` 推送，自动触发 `hisense_washer_complete` 总线事件与系统持久化通知。
3. **零冲突互踢**：无论您何时在手机上打开、关闭或在后台切换「海信爱家」App，Home Assistant 的 MQTT 长连接始终保持稳定在线，双方互不影响！

---

## 4. FAQ & Troubleshooting / 常见问题与排错

### Q1: Home Assistant 登录时提示“登录失败 (invalid_auth)”？
* **原因**：副账号密码输入错误，或副账号尚未在海信爱家 App 中设置静态密码。
* **解决方法**：请在手机 App 中用该副账号登录一次，并在 **设置 -> 账号与安全** 中重新设置密码，然后用新密码在 HA 中重试。

### Q2: 登录成功后提示“未找到设备 (no_devices)”或设备列表为空？
* **原因**：副账号尚未加入包含设备的家庭，或者被加入到了一个空的家庭中。
* **解决方法**：请主账号打开 App 确认副账号是否在正确的家庭中；若有多个家庭，确保在 HA 配置流的“选择家庭”步骤中选中了设备所在的家庭。

### Q3: 副账号是否会影响主账号的质保与售后？
* **解答**：完全不会。设备的购买记录、电子发票和官方售后绑定依然归属于主账号。家庭成员共享仅授予家电设备的局域网/远程控制与状态查看权限。
