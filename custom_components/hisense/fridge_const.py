"""AIHome refrigerator commands, control limits, mode values, and alarm keys.

Command names and limits were verified on BCD-516WD1FPA-EQ51.
DBDDegerming has no Set prefix; temperature parameter keys use flat camel case.
"""

COMMAND_PREFIX = "connector.device.command."

SET_REFRIGERATOR_TEMPERATURE = COMMAND_PREFIX + "SetTemperature.Refrigerator"

SET_FREEZE_TEMPERATURE = COMMAND_PREFIX + "SetTemperature.Freeze"

SET_MODE_SMART = COMMAND_PREFIX + "SetModes.Smart"

SET_MODE_QUICK_COOLING = COMMAND_PREFIX + "SetModes.QuickCooling"

SET_VARIATION_TEMP_SPACE_DRAWER = COMMAND_PREFIX + "SetVariationTempSpaceDrawer"

DBD_DEGERMING = COMMAND_PREFIX + "DBDDegerming"

PARAM_REFRIGERATOR_SET_TEMPERATURE = "refrigeratorSetTemperature"

PARAM_FREEZE_SET_TEMPERATURE = "freezeSetTemperature"

PARAM_SMART_MODE_SWITCH = "smartModeSwitch"

PARAM_QUICK_COOLING_MODE_SWITCH = "quickCoolingModeSwitch"

PARAM_VARIATION_TEMP_SPACE_DRAWER = "variationTempSpaceDrawer"

PARAM_DBD_DEGERMING = "dBDDegerming"

WORK_MODE_COMMANDS: dict[str, tuple[str, str]] = {
    "SMART": (SET_MODE_SMART, PARAM_SMART_MODE_SWITCH),
    "QUICK_COOLING": (SET_MODE_QUICK_COOLING, PARAM_QUICK_COOLING_MODE_SWITCH),
}

MODE_SWITCH_ON = "1"

MODE_SWITCH_OFF = "0"

VARIATION_TEMP_SPACE_VALUES: dict[int, str] = {
    0: "原鲜",       # OriginalFresh1
    1: "0℃养鲜",     # FreshFood1
    2: "母婴",       # Infant1
}

REFRIGERATOR_SET_TEMP_MIN = 2

REFRIGERATOR_SET_TEMP_MAX = 8

FREEZE_SET_TEMP_MIN = -25

FREEZE_SET_TEMP_MAX = -15

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

UNSUPPORTED_ALARM_VALUE = "--"
