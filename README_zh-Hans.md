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


## 状态同步

本集成与海信 **AIHome 云端** 通信。设备状态会在初始化、实体操作后或按下「刷新状态」时读取。

每台设备在「诊断」类实体中提供一个 **刷新状态** 按钮，用于向 AIHome 云端 **请求一次当前状态**。每次按下都会产生真实的云端访问，请不要用自动化做成高频轮询。

若你需要 **实时状态**，推荐将同一台海信设备 **同时接入米家**，在 Home Assistant 里使用 [XiaomiMiot](https://github.com/al-one/hass-xiaomi-miot) 或 [XiaomiHome](https://github.com/xiaomi/ha_xiaomi_home) 订阅米家侧的状态变化，再通过 **自动化** 在小米实体变化时 **调用本集成对应设备的「刷新状态」按钮**，从而间接同步海信实体。

## 冰箱可视化卡片（集成自带）

自 v1.8.0 起，集成自带冰箱可视化卡片（`hisense-fridge-card`），并在启动时**自动注册**，无需手动添加前端资源。卡片在冰箱示意图上展示冷藏 / 冷冻 / 变温三区温度，支持门未关告警角标，并可直接切换工作模式、变温档位、除菌+净味；点击分区可打开对应实体详情。

**GUI 模式**（推荐）：重启后在仪表盘「添加卡片 → 手动」粘贴：

```yaml
type: custom:hisense-fridge-card
# name_prefix: hai_xin_bing_xiang   # 实体 ID 前缀（默认如上）
# name: 海信冰箱                     # 卡片标题，留空自动取设备名
# image: /hisense/hisense-fridge.png # 示意图，默认集成自带
# entities:                          # 可选：逐项覆盖实体
#   fridgeActual: sensor.hai_xin_bing_xiang_temperature_refrigerator_actual
```

全部实体默认由 `name_prefix` 拼出，可在卡片编辑器里逐项覆盖。

> 注：默认前缀对应海信品牌冰箱（如 `hai_xin_bing_xiang`）。v1.7.9 起支持的其他品牌（如容声）实体前缀不同，请在卡片编辑器里修改 `name_prefix` 或逐项覆盖实体。

**YAML 模式仪表盘**（Lovelace 资源表只读时）：集成会通过 `extra_js_url` 自动注入；若卡片未出现，请在 `configuration.yaml` 手动声明一次资源：

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /hisense/hisense-fridge-card.js?v=1.8.0
      type: module
```

> 提示：升级集成后若卡片样式未更新，请硬刷新浏览器（Ctrl/Cmd+Shift+R）。
