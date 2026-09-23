import asyncio

from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PASSWORD, CONF_USERNAME, DOMAIN
from .coordinator import HisenseDataUpdateCoordinator
from .pyhisenseapi import HiSenseAC, HiSenseFridge, HiSenseWasher


async def async_setup_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    session = async_get_clientsession(hass)
    clients = []
    coordinators = []
    token_lock = asyncio.Lock()

    def save_tokens(access_token, refresh_token, customer_id):
        """Keep every device and the config entry on the same token pair."""
        for client in clients:
            client.access_token = access_token
            client.refresh_token = refresh_token
            client.customer_id = customer_id
        devices = [
            {
                **device,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "customer_id": customer_id,
            }
            for device in entry.data["devices"]
        ]
        hass.config_entries.async_update_entry(entry, data={**entry.data, "devices": devices})

    username = entry.data.get(CONF_USERNAME, "")
    password = entry.data.get(CONF_PASSWORD, "")
    if not username or not password:
        entry.async_start_reauth(hass)

    for device_info in entry.data["devices"]:
        device_id = device_info["device_id"]
        wifi_id = device_info["wifi_id"]
        refresh_token = device_info["refresh_token"]
        access_token = device_info.get("access_token")
        customer_id = device_info.get("customer_id", "")
        partner_id = device_info.get("partner_id", "1001")
        home_id = device_info.get("home_id", "")
        device_type = device_info.get("device_type", "空调")
        device_type_name = device_info.get("device_type_name", "")
        device_name = device_info.get("device_name", "")
        device_code = device_info.get("device_code", "")

        friendly_name = (
            f"{device_type_name}_{device_name}"
            if device_type_name and device_name
            else device_id
        )
        entity_name = device_code if device_code else device_id

        if device_type == "洗衣机":
            client = HiSenseWasher(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        elif device_type == "冰箱":
            client = HiSenseFridge(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )
        else:
            client = HiSenseAC(
                wifi_id=wifi_id,
                device_id=device_id,
                refresh_token=refresh_token,
                session=session,
                device_name=friendly_name,
                entity_name=entity_name,
                home_id=home_id,
                access_token=access_token,
                customer_id=customer_id,
                partner_id=partner_id,
                username=username,
                password=password,
                on_token_refresh=save_tokens,
                token_lock=token_lock,
            )

        clients.append(client)
        coordinator = HisenseDataUpdateCoordinator(hass, client, device_type, entry)
        client.on_auth_failure = coordinator.async_start_refresh
        coordinators.append((device_id, coordinator))

    for device_id, coordinator in coordinators:
        hass.data[DOMAIN][entry.entry_id][device_id] = coordinator
        coordinator.async_start_refresh()

    platforms = [
        "climate",
        "switch",
        "button",
        "number",
        "sensor",
        "binary_sensor",
        "select",
    ]
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: config_entries.ConfigEntry):
    platforms = [
        "climate",
        "switch",
        "button",
        "number",
        "sensor",
        "binary_sensor",
        "select",
    ]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unload_ok:
        for coordinator in hass.data[DOMAIN].get(entry.entry_id, {}).values():
            await coordinator.async_cancel_refresh()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
