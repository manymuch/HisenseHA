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
