"""Support for VyOS Routers."""

import logging

from .const import (
    ENTRIES_VERSION,
    CONF_DETECTION_TIME,
    DOMAIN,
    CONF_TRACKER_INTERFACE,
    CONF_CONFIG_VERSION_DHCP_SERVER,
    DEFAULT_CONFIG_VERSION_DHCP_SERVER,
    KEY_COORDINATOR,
    PLATFORMS,
    UPDATE_LISTENER,
    VYOS_API,
)
from .router import VyOSApiDataUpdateCoordinator
from .vyosapi import VyOSApi, VyOSApiError


from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers import aiohttp_client
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entries merging all of them in one."""
    new_version = ENTRIES_VERSION
    if config_entry.version == 1:
        _LOGGER.debug("Migrating config entry from version %s", config_entry.version)
        new_data = config_entry.data.copy()
        new_data[CONF_CONFIG_VERSION_DHCP_SERVER] = DEFAULT_CONFIG_VERSION_DHCP_SERVER
        config_entry.version = new_version
        hass.config_entries.async_update_entry(config_entry, data=new_data)
    _LOGGER.info(
        "Entry %s successfully migrated to version %s.",
        config_entry.entry_id,
        new_version,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up VyOS from a config entry."""
    conf = config_entry.data
    url: str = conf[CONF_URL]
    api_key: str = conf[CONF_API_KEY]
    verify_ssl: bool = conf[CONF_VERIFY_SSL]
    tracker_interfaces_input: str = conf[CONF_TRACKER_INTERFACE]
    tracker_interfaces = [
        iface.strip() for iface in tracker_interfaces_input.split(",")
    ]
    detection_time: list[str] = conf[CONF_DETECTION_TIME]

    session = aiohttp_client.async_get_clientsession(hass)
    vyos_api = VyOSApi(session, url, api_key, verify_ssl)

    try:  # test if the api is sucessful
        await vyos_api.get_present_arp_clients(tracker_interfaces)
    except VyOSApiError:
        _LOGGER.exception("Failure while connecting to VyOS API endpoint")
        return False

    if len(tracker_interfaces) > 0:
        # Verify that specified tracker interfaces are valid
        interfaces = await vyos_api.list_interfaces()
        for interface in tracker_interfaces:
            if interface not in interfaces:
                _LOGGER.error(
                    "Specified VyOS tracker interface %s is not found", interface
                )
                return False

    coordinator = VyOSApiDataUpdateCoordinator(hass, config_entry, vyos_api)
    # await hass.async_add_executor_job(coordinator.api.get_hub_details)
    await coordinator.async_config_entry_first_refresh()

    # device_registry = dr.async_get(hass)
    # device_registry.async_get_or_create(
    #     config_entry_id=config_entry.entry_id,
    #     connections={(DOMAIN, coordinator.serial_num)},
    #     manufacturer=ATTR_MANUFACTURER,
    #     model=coordinator.model,
    #     name=coordinator.hostname,
    #     sw_version=coordinator.firmware,
    # )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {
        VYOS_API: vyos_api,
        CONF_TRACKER_INTERFACE: tracker_interfaces,
        KEY_COORDINATOR: coordinator,
    }

    try:
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    except:
        hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    update_listener = config_entry.add_update_listener(async_update_options)
    hass.data[DOMAIN][config_entry.entry_id][UPDATE_LISTENER] = update_listener

    return True


async def async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        update_listener = hass.data[DOMAIN][entry.entry_id][UPDATE_LISTENER]
        update_listener()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
