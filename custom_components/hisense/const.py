"""Constants for HiSense Integration."""
DOMAIN = "hisense"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"


def climate_limits_signal(device_id: str) -> str:
    """Dispatcher signal when per-device climate min/max limits change."""
    return f"{DOMAIN}_climate_limits_{device_id}"


def device_suggested_object_id(device_id: str, suffix: str) -> str:
    """Suggested entity object_id segment: slugified device id + role (for new entities)."""
    from homeassistant.util import slugify

    return f"{suffix}_{slugify(device_id)}"


# --------------------------------------------------------------------------
# 集成自带 Lovelace 卡片（自动注册）
# --------------------------------------------------------------------------

#: 卡片 js 文件名（随集成发布在 custom_components/hisense/www/ 下）
CARD_JS_FILENAME = "hisense-fridge-card.js"

#: 冰箱示意图文件名（卡片默认引用）
CARD_IMAGE_FILENAME = "hisense-fridge.png"

#: 通过 HA HTTP 静态路径对外暴露的 URL：/<domain>/<file>
CARD_URL_PATH = f"/{DOMAIN}/{CARD_JS_FILENAME}"
CARD_IMAGE_URL_PATH = f"/{DOMAIN}/{CARD_IMAGE_FILENAME}"

#: 仪表盘里写 type: custom:hisense-fridge-card
CARD_ELEMENT_NAME = "hisense-fridge-card"

#: 旧的手工部署地址前缀：自动识别用户此前手动添加的资源并迁移/去重，
#: 避免同一张卡片被加载两次（表现为卡片行为异常、改动不生效）。
CARD_LEGACY_URL_PREFIXES = (
    "/local/community/hisense-fridge-card/",
    "/local/hisense/",
    "/local/hisense-fridge-card.js",
    "/hacsfiles/hisense-fridge-card/",
)
