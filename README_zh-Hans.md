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
4. 选择设备所在的 **家庭**。
5. 勾选要添加的一台或多台 **设备**，完成向导。


## 欧洲 HiSmart Life 账户

添加集成时选择 **Europe (HiSmart Life / Ayla)**，使用欧洲 HiSmart Life
账户登录。默认的 **China (HisenseHA)** 选项及没有区域字段的现有配置继续
使用原来的 AIHome 流程。

欧洲后端目前仅支持 **Smart-1-110** 分体空调配置（已在 Hisense TQ35XE0CG
上确认）。不支持其他设备配置、移动空调、冰箱、洗衣机或干衣机。欧洲流程
直接选择设备，不经过 AIHome 的家庭选择步骤。

提供开关机、制冷/制热/除湿/送风/自动模式、16–32 °C 整数设定温度、室温、
七档风速、显示屏开关和手动刷新。暂不提供摆风、定时和辅助加热，也不定期轮询。
欧洲账户的密码仅用于登录，不保存在配置项中；访问令牌和刷新令牌保存在
Home Assistant 的本地配置存储中。会话失效后可在欧洲专用流程中重新认证。

已验证真实账户的登录、设备及属性读取，以及 Home Assistant 配置加载。
实体控制和真实令牌续期仍需现场验证。启用自动化前，请先核对手机应用的状态，
再观察设备并测试、恢复单个设置。安装不会发送控制命令。请勿分享账户密码、
令牌或原始 HTTP 调试日志。

## 状态同步

本集成与海信 **AIHome 云端** 通信。设备状态会在初始化、实体操作后或按下「刷新状态」时读取。

每台设备在「诊断」类实体中提供一个 **刷新状态** 按钮，用于向 AIHome 云端 **请求一次当前状态**。每次按下都会产生真实的云端访问，请不要用自动化做成高频轮询。

若你需要 **实时状态**，推荐将同一台海信设备 **同时接入米家**，在 Home Assistant 里使用 [XiaomiMiot](https://github.com/al-one/hass-xiaomi-miot) 或 [XiaomiHome](https://github.com/xiaomi/ha_xiaomi_home) 订阅米家侧的状态变化，再通过 **自动化** 在小米实体变化时 **调用本集成对应设备的「刷新状态」按钮**，从而间接同步海信实体。
