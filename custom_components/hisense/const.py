"""Constants for HiSense Integration."""
DOMAIN = "hisense"

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Options keys for washer dynamic polling
CONF_ENABLE_WASHER_POLL = "enable_washer_dynamic_poll"
CONF_WASHER_POLL_INTERVAL = "washer_poll_interval"
DEFAULT_ENABLE_WASHER_POLL = False
DEFAULT_WASHER_POLL_INTERVAL = 5  # minutes
MIN_WASHER_POLL_INTERVAL = 5  # minutes (强制不得小于5分钟以防封号)

# Options keys for periodic polling compensation (refrigerator, wine cabinet, water heater)
CONF_ENABLE_PERIODIC_POLL = "enable_periodic_poll"
DEFAULT_ENABLE_PERIODIC_POLL = False  # 默认关闭以防封号，依赖 MQTT 实时推送


def climate_limits_signal(device_id: str) -> str:
    """Dispatcher signal when per-device climate min/max limits change."""
    return f"{DOMAIN}_climate_limits_{device_id}"


def device_suggested_object_id(device_id: str, suffix: str) -> str:
    """Suggested entity object_id segment: slugified device id + role (for new entities)."""
    from homeassistant.util import slugify

    return f"{suffix}_{slugify(device_id)}"
