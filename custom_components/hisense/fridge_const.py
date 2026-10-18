"""海信 AIHome 冰箱命令 / 状态字典。

本模块集中保存冰箱的控制命令名、参数键名、状态键名与取值映射，
供 ``HiSenseFridge`` 及各实体平台直接引用，避免在业务代码里散落魔法字符串。

数据来源：微信小程序 + App 真实抓包（2026-10-11 / 2026-10-18），设备
``BCD-516WD1FPA-EQ51``（productCode ``LB051600602J``），全部命令均实测返回
``SUCCESS``。

命名规律::

    connector.device.command.<能力名>[.<子功能后缀>]

- 温度类带区域后缀（``SetTemperature.Refrigerator`` / ``SetTemperature.Freeze``）
- 模式类带模式后缀（``SetModes.Smart`` / ``SetModes.QuickCooling``）
- 抽屉不带后缀（``SetVariationTempSpaceDrawer``）
- 除菌**没有 Set 前缀**（``DBDDegerming``），是唯一的例外

点号后缀拼接后等于 layout 接口的 ``modelFunction``，例如
``connector.device.function.Modes.Smart`` ↔ ``connector.device.command.SetModes.Smart``。
"""

from __future__ import annotations

# ============================================================================
# 命令名前缀
# ============================================================================

COMMAND_PREFIX = "connector.device.command."


# ============================================================================
# 冰箱控制命令（全部已实测确认）
# ============================================================================
# 结构：动作 → (command, params 模板)
# params 模板的 value 由调用方填充时用 ``.format`` / 字典展开均可。

#: 冷藏室设定温度。参数键为 ``refrigeratorSetTemperature``（扁平驼峰，勿用点号）。
SET_REFRIGERATOR_TEMPERATURE = COMMAND_PREFIX + "SetTemperature.Refrigerator"

#: 冷冻室设定温度。参数键为 ``freezeSetTemperature``。
SET_FREEZE_TEMPERATURE = COMMAND_PREFIX + "SetTemperature.Freeze"

#: 智能模式开关。参数键 ``smartModeSwitch``，值 "1"=开 / "0"=关。
SET_MODE_SMART = COMMAND_PREFIX + "SetModes.Smart"

#: 速冷模式开关。参数键 ``quickCoolingModeSwitch``，值 "1"=开 / "0"=关。
SET_MODE_QUICK_COOLING = COMMAND_PREFIX + "SetModes.QuickCooling"

#: 变温空间档位。参数键 ``variationTempSpaceDrawer``，取值见
#: :data:`VARIATION_TEMP_SPACE_VALUES`。
SET_VARIATION_TEMP_SPACE_DRAWER = COMMAND_PREFIX + "SetVariationTempSpaceDrawer"

#: DBD 除菌（离子除菌）启停。参数键 ``dBDDegerming``，值 "1"=开始 / "0"=停止。
#: ⚠️ 唯一不带 ``Set`` 前缀的冰箱命令。
DBD_DEGERMING = COMMAND_PREFIX + "DBDDegerming"


# ============================================================================
# 控制参数键名
# ============================================================================

PARAM_REFRIGERATOR_SET_TEMPERATURE = "refrigeratorSetTemperature"
PARAM_FREEZE_SET_TEMPERATURE = "freezeSetTemperature"
PARAM_SMART_MODE_SWITCH = "smartModeSwitch"
PARAM_QUICK_COOLING_MODE_SWITCH = "quickCoolingModeSwitch"
PARAM_VARIATION_TEMP_SPACE_DRAWER = "variationTempSpaceDrawer"
PARAM_DBD_DEGERMING = "dBDDegerming"


# ============================================================================
# 模式定义（本机实现的两种：智能 / 速冷）
# ============================================================================

#: 工作模式 → (command, params 键)
WORK_MODE_COMMANDS: dict[str, tuple[str, str]] = {
    "SMART": (SET_MODE_SMART, PARAM_SMART_MODE_SWITCH),
    "QUICK_COOLING": (SET_MODE_QUICK_COOLING, PARAM_QUICK_COOLING_MODE_SWITCH),
}

#: 模式下发的 value 语义（开关）
MODE_SWITCH_ON = "1"
MODE_SWITCH_OFF = "0"


# ============================================================================
# 变温空间档位（本机 VariationTempSpace）
# ============================================================================

#: 变温空间取值 → 语义（来自 layout 的 modelCombFunction.subFunction）
VARIATION_TEMP_SPACE_VALUES: dict[int, str] = {
    0: "原鲜",       # OriginalFresh1
    1: "0℃养鲜",     # FreshFood1
    2: "母婴",       # Infant1
}

#: 语义 → 取值
VARIATION_TEMP_SPACE_REVERSE: dict[str, int] = {
    name: value for value, name in VARIATION_TEMP_SPACE_VALUES.items()
}

#: 兼容旧 API 命名（本地原 ``variation_mode_lookup`` 的英文名）
VARIATION_TEMP_SPACE_ALIASES: dict[str, int] = {
    "ORIGINAL_FRESH": 0,
    "ZERO_C_FRESH": 1,
    "INFANT": 2,
}


# ============================================================================
# 温度设定范围
# ============================================================================
# 已由 `/4.0/iot/devices/function/getHomepageConfig` 确证（attribute.value）：
#     refrigeratorSetTemperature = [2, 8]
#     freezeSetTemperature       = [-25, -15]
# 同一响应还给了面板显示温度范围（不是设定范围，勿混）：
#     displayTemperature.refrigerator = [0, 15]
#     displayTemperature.freeze       = [-40, -10]

#: 冷藏设定温度范围 [2, 8]℃
REFRIGERATOR_SET_TEMP_MIN = 2
REFRIGERATOR_SET_TEMP_MAX = 8

#: 冷冻设定温度范围 [-25, -15]℃
FREEZE_SET_TEMP_MIN = -25
FREEZE_SET_TEMP_MAX = -15

#: 冷藏面板显示温度（sensor 合理区间，仅用于判断读数是否可信）
REFRIGERATOR_DISPLAY_TEMP_MIN = 0
REFRIGERATOR_DISPLAY_TEMP_MAX = 15

#: 冷冻面板显示温度（sensor 合理区间）
FREEZE_DISPLAY_TEMP_MIN = -40
FREEZE_DISPLAY_TEMP_MAX = -10


# ============================================================================
# 状态键名（states 字典，直接按 key 取值，勿解析数组）
# ============================================================================

# ---- 温度：注意区分「设定值 / 实际值 / 显示值」三种前缀 ----

#: 冷藏设定温度（number 读写）
STATE_REFRIGERATOR_SET_TEMPERATURE = "refrigeratorSetTemperature"
#: 冷藏设定温度的点号别名（与上面等价）
STATE_REFRIGERATOR_SET_TEMPERATURE_ALT = "setTemperature.refrigerator"
#: 冷藏实际温度（sensor）
STATE_REFRIGERATOR_REAL_TEMPERATURE = "refrigeratorRealTemperature"
#: 冷藏面板显示温度
STATE_REFRIGERATOR_DISPLAY_TEMPERATURE = "displayTemperature.refrigerator"

#: 冷冻设定温度（number 读写）
STATE_FREEZE_SET_TEMPERATURE = "freezeSetTemperature"
#: 冷冻设定温度的点号别名
STATE_FREEZE_SET_TEMPERATURE_ALT = "setTemperature.freeze"
#: 冷冻实际温度（sensor）
STATE_FREEZE_REAL_TEMPERATURE = "freezeRealTemperature"
#: 冷冻面板显示温度
STATE_FREEZE_DISPLAY_TEMPERATURE = "displayTemperature.freeze"

# ---- 开关 / 在线 ----

#: 冰箱开关，1=开
STATE_REFRIGERATOR_ON = "refrigeratorOn"
#: 在线状态，1=在线
STATE_ONLINE_STATUS = "onlineStatus"

# ---- 模式：用布尔位，勿用 workMode 总编码 ----

#: 工作模式总编码。⚠️ 本机返回 "0" 或 "--"，语义不可靠，勿用于判断。
STATE_WORK_MODE = "workMode"
#: 智能模式位，1=开
STATE_WORK_MODE_SMART = "workMode.Smart"
#: 速冷模式位，1=开
STATE_WORK_MODE_QUICK_COOLING = "workMode.QuickCooling"

# ---- 变温空间 ----

#: 变温空间档位，取值见 VARIATION_TEMP_SPACE_VALUES
STATE_VARIATION_TEMP_SPACE_DRAWER = "variationTempSpaceDrawer"

# ---- 净化 / 除菌 ----

STATE_DEGERMING_SWITCH = "degermingSwitch"
STATE_CLEANER_SWITCH = "cleanerSwitch"
STATE_DBD_DEGERMING = "dBDDegerming"

# ---- 其他 ----

STATE_COMPRESSOR_FREQUENCY = "compressorFrequency"
#: 机型不支持时该键可能返回 "--"，应判 unknown 而非 0
UNSUPPORTED_STATE_VALUE = "--"


# ============================================================================
# 冰箱告警键（detail 的 states → 中文说明）
# ============================================================================
# 来源：layout 接口「异常消息」列的 modelCombFunction.subFunction，
# 命名空间 connector.device.function.Alarm.Fridge。
#
# ★ 重要：告警**从 detail 接口的 states 直接读取**，不走独立接口。
#   独立的 /4.0/iot/databoard/fridge/alarmState/query 实测
#   alarmStateCodeList 恒为空，已废弃不用。
#
# 取值语义：
#   "0"  = 正常
#   "1"  = 异常
#   "--" = 机型不支持 → 实体仍会创建，但显示 unavailable
#
# ⚠️ 反向不成立：值为 "0" 不能证明机型支持该功能。本机没有制冰机，
#    iceMakerWaterLackAlarm 仍返回 "0"；layout 也照样给出"制冰开关"栏目
#    （layout 是产品模板，不是本机硬件清单）。判断"有没有"只能靠实物或实测。

FRIDGE_ALARM_CODES: dict[str, str] = {
    # 门未关（也用作门开/关状态：0=关好 / 1=未关）
    "refriOpenDoorAlarm": "冷藏室门未关",
    "freezeOpenDoorAlarm": "冷冻室门未关",
    "variaOpenDoorAlarm": "变温室门未关",
    "wideOpenDoorAlarm": "宽温室门未关",
    # 门未关严
    "refriLeftOpenDoorAlarm": "冷藏门未关严",
    "freezeLeftOpenDoorAlarm": "冷冻门未关严",
    # 超温
    "freezeOverTempAlarm": "冷冻室超温",
    "variaOverTempAlarm": "变温室超温",
    "wideOverTempAlarm": "宽温室超温",
    #: 字典里只有 _high / _low 两个，这个裸名是遗留项，本机恒为 "--"。
    "refriOverTempAlarm": "冷藏室超温",
    "refriOverTempAlarm_high": "冷藏室超温(偏高)",
    "refriOverTempAlarm_low": "冷藏室超温(偏低)",
    # 制冰 / 水位
    "iceMakerWaterLackAlarm": "制冰储水盒缺水",
    #: 字典里查不到这个键，本机有值但语义未证实（疑似补水盒缺水）。
    "hydropeniaAlarm": "缺水告警",
    # 气味
    "mildOdorAlarm": "冷藏室轻微异味",
    "severeOdorAlarm": "冷藏室气味过大",
}

#: 机型不支持时 states 该键返回的值
UNSUPPORTED_ALARM_VALUE = "--"


# ============================================================================
# 故障码（states 中 0=正常 / 1=故障 的键）
# ============================================================================

FRIDGE_FAULT_STATES: tuple[str, ...] = (
    "wifiModuleFault",
    "iceMakerFault",
    "odorSensorFault",
    "waterTankInstFault",
    "humiSensorFault",
    "tempSensorFault",
    "rightFreezeSensorFault",
    "wineSensorFault",
    "refriSensorFault",
    "freezeSensorFault",
    "variaSensorFault",
    "wideSensorFault",
    "condensationFanFault",
    "refriFanFault",
    "freezeFanFault",
    "variaFanFault",
    "wideFanFault",
    "refriEvaporatorSensorFault",
    "freezeEvaporatorSensorFault",
    "variaEvaporatorSensorFault",
    "wideEvaporatorSensorFault",
    "dryWetDrawerSensorFault",
    "variaTempDrawerSensorFault",
    "iceInletPipeSensorFault",
    "iceSensorFailure",
    "iceTempSensorFailure",
    "ambientLightSensorError",
    "refriDamperFault",
    "electricValveSwitchFreezeFault",
    "electricValveSwitchRefriFault",
    "freezeCapillaryCloggingFault",
    "refriCapillaryCloggingFault",
    "freezeDefrostingHeaterFault",
    "duraTempSensorError",
    "rxFailure",
    "txFailure",
    "frzDoorSensorError",
    "frzDoorSensorFault",
    "refDoorSensorError",
    "refDoorSensorFault",
)


# ============================================================================
# 行为说明（供开发者参考）
# ============================================================================
# 1. 改温度会退出模式：执行 SET_REFRIGERATOR_TEMPERATURE 或
#    SET_FREEZE_TEMPERATURE 后，workMode.Smart / workMode.QuickCooling 会归 0
#    （设备固件行为，进入"自定义"模式）。调用后需同步刷新模式状态。
# 2. 模式判断用布尔位 STATE_WORK_MODE_SMART / STATE_WORK_MODE_QUICK_COOLING，
#    勿用 STATE_WORK_MODE。
# 3. 直接按 states key 取值，勿解析 originalState 逗号数组。
#    数组下标 [0] 冷藏设定 / [1] 冷冻设定 / [4] 开关 / [11] 变温 与新 key 一致；
#    [3] 模式语义已变；[9] 环境温度新 API 无对应键。
# 4. 控制成功的响应会顺带回传完整 states，可直接刷新实体，省一次 detail 请求。
