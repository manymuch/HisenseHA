# 海信智能家居（HisenseHA）
![Hisense](hisense-electronics.png)

[English](README.md)


面向 **海信（Hisense）** 智能设备的 Home Assistant 自定义集成，使用云端api接口，目前支持空调和洗衣机  



## 环境要求

- **Home Assistant** 2025.6 或更高版本（若使用更旧的核心，请查看[发行说明](https://github.com/manymuch/HisenseHA/releases)）。
- 能在官方手机 **海信爱家 App** 中正常登录的海信账号（用户名与密码一致）。
- 空调、冰箱或受支持的洗衣机需已在 App 中完成配网，并归属到某个 **家庭**。

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


## 状态同步

本集成与海信 **AIHome 云端** 通信。设备状态会在初始化、实体操作后或按下「刷新状态」时读取。

每台设备在「诊断」类实体中提供一个 **刷新状态** 按钮，用于向 AIHome 云端 **请求一次当前状态**。每次按下都会产生真实的云端访问，请不要用自动化做成高频轮询。

若你需要 **实时状态**，推荐将同一台海信设备 **同时接入米家**，在 Home Assistant 里使用 [XiaomiMiot](https://github.com/al-one/hass-xiaomi-miot) 或 [XiaomiHome](https://github.com/xiaomi/ha_xiaomi_home) 订阅米家侧的状态变化，再通过 **自动化** 在小米实体变化时 **调用本集成对应设备的「刷新状态」按钮**，从而间接同步海信实体。
