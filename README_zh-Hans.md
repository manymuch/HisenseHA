# 海信智能家居（HisenseHA）
![Hisense](hisense-electronics.png)

[English](README.md)


面向 **海信（Hisense）** 智能设备的 Home Assistant 自定义集成，使用云端 API，目前支持空调、洗衣机、干衣机和冰箱。



## 环境要求

- **Home Assistant** 2025.6 或更高版本（若使用更旧的核心，请查看[发行说明](https://github.com/manymuch/HisenseHA/releases)）。
- 能在官方手机 **海信爱家 App** 中正常登录的海信账号（用户名与密码一致）。
- 空调、冰箱、受支持的洗衣机或干衣机需已在 App 中完成配网，并归属到某个 **家庭**。

## 安装集成

### 方式一：HACS

[![Open your Home Assistant instance and add this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=manymuch&repository=HisenseHA&category=integration)

点上面的按钮一键添加，或者手动操作：

1. 在 Home Assistant 中打开 **HACS**。
2. 进入 **集成** → 右上角菜单（⋮）→ **自定义仓库**。
3. 添加仓库 `https://github.com/manymuch/HisenseHA`，类别选 **集成（Integration）**。
4. 在 **Hisense Smart Devices** 卡片中点击 **下载**。
5. 按提示 **重启** Home Assistant。

### 方式二：手动安装

1. 将 Release 中的文件解压后复制到 Home Assistant 配置目录下：

   `config/custom_components/hisense/`

2. **重启** Home Assistant。

## 添加设备

1. 打开 **设置** → **设备与服务** → **添加集成**。
2. 搜索 **Hisense Smart Devices**（或 **Hisense**）并选择。
3. 输入 **海信爱家 App 的用户名和密码**（若错误会提示认证失败）。
   > 💡 **推荐方案（防互踢 · 0 抓包）**：为彻底避免 Home Assistant 与手机官方 App 发生 MQTT 会话冲突抢占互踢，强烈建议在海信爱家 App 中通过「家庭成员共享」为 HA 配置一个专属副账号。请参阅详细图文教程：[海信爱家家庭副账号共享配置指引](docs/SUB_ACCOUNT_GUIDE.md)。
4. 选择设备所在的 **家庭**。
5. 勾选要添加的一台或多台 **设备**，完成向导。


## 状态同步与实时推送

本集成与海信 **AIHome 云端** 通信，并内置了海信云端 **MQTT 长连接推送监听**：
1. **实时推送**：集成启动后会自动与海信 MQTT 推送服务器保持长连接，实时接收洗衣机运行状态、洗涤进度变更以及“洗衣完成”等事件。
   - 当检测到洗衣完成时，会自动在 Home Assistant 发送持久化通知，并在系统总线上触发 `hisense_washer_complete` 事件，方便直接联动手机推送或音箱播报播发“洗衣服已完成”。
   - 收到任意推送时触发 `hisense_mqtt_message` 事件。
2. **主动刷新**：在实体操作后或按下「刷新状态」诊断按钮时，也会立即向云端发起一次状态更新。

> 💡 **开发者参考文档**：关于海信云端 MQTT Broker 端点、网关签名鉴权、主题订阅矩阵以及全品类设备（洗衣机、干衣机、空调、冰箱、洗碗机、蒸烤箱）的消息载荷解析规范与最佳实践，请参阅技术文档：[海信云端 MQTT 实时推送协议与多设备对接指南](docs/MQTT_PROTOCOL.md)。

## 功能特性

- **空调**：开关机、模式（制冷/制热/送风/除湿）、目标温度、风速等。
- **冰箱**：各温区温度监测、速冷/速冻模式控制、杀菌开关、智能降噪等。
- **洗衣机**（双向监控与控制）：
  - **开关控制**：电源开关、启动/暂停、洗涤运转童锁。
  - **程序选择**：支持 37 种预置洗涤程序（混合、单烘、AI洗烘、羽绒、羊毛、速净、空气洗等）。
  - **投放调节**：洗涤剂与柔顺剂自动投放量（智能/多/标准/少/关闭）。
  - **参数设置**：洗涤水温（冷水~95℃）、洗涤时间长度、漂洗次数（1~5次）、脱水转速（0~1400转，烘干时自动联动固件安全转速）。
  - **烘干调节**：即穿、即熨、即存、定时烘干（30分钟~4小时），以及低温烘（单烘程序下专属协同）。
- **干衣机**：运行状态、剩余时间、烘干档位与温度等只读监控。
