"""Config flow for VyOS integration."""

import logging
import voluptuous as vol

from .const import (
    CONF_DETECTION_TIME,
    get_data_schema,
    DOMAIN,
    CONF_TRACKER_INTERFACE,
    CONF_URL,
    CONF_API_KEY,
    CONF_VERIFY_SSL,
    CONF_CONFIG_VERSION_DHCP_SERVER,
)
from .vyosapi import VyOSApi, VyOSApiError

from homeassistant import config_entries, core
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = aiohttp_client.async_get_clientsession(hass)

    conf = data
    url: str = conf[CONF_URL]
    api_key: str = conf[CONF_API_KEY]
    verify_ssl: bool = conf[CONF_VERIFY_SSL]
    cofnig_dhcp_server_version: int = conf[CONF_CONFIG_VERSION_DHCP_SERVER]
    # config flow can't handle list
    tracker_interfaces_input: str = conf[CONF_TRACKER_INTERFACE]
    tracker_interfaces = [
        iface.strip() for iface in tracker_interfaces_input.split(",")
    ]
    detection_time: list[str] = conf[CONF_DETECTION_TIME]

    session = aiohttp_client.async_get_clientsession(hass)
    vyos_api = VyOSApi(session, url, api_key, verify_ssl)

    try:
        await vyos_api.get_present_arp_clients(tracker_interfaces)
    except Exception as err:
        _LOGGER.exception("Failure while connecting to VyOS API endpoint")
        raise VyOSApiError from err

    if len(tracker_interfaces) > 0:
        # Verify that specified tracker interfaces are valid
        interfaces = await vyos_api.list_interfaces()
        for interface in tracker_interfaces:
            if interface not in interfaces:
                _LOGGER.error(
                    "Specified VyOS tracker interface %s is not found", interface
                )
                raise VyOSApiError(
                    "Specified VyOS tracker interface %s is not found".format(interface)
                )

    # Return info that you want to store in the config entry.
    return {
        "title": f"VyOS - {url}",
        CONF_URL: url,
        CONF_API_KEY: api_key,
        CONF_CONFIG_VERSION_DHCP_SERVER: cofnig_dhcp_server_version,
        CONF_VERIFY_SSL: verify_ssl,
        CONF_TRACKER_INTERFACE: tracker_interfaces_input,
        CONF_DETECTION_TIME: detection_time,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for vyos-router."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            await self.async_set_unique_id(
                user_input[CONF_URL] + user_input[CONF_API_KEY]
            )
            self._abort_if_unique_id_configured()

            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except VyOSApiError:
                errors["base"] = "invalid config"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=get_data_schema(), errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manage the options."""
        errors = {}
        if user_input is None:
            user_input = {}

        data = self.config_entry.data

        filled_data_schema = get_data_schema(
            default_CONF_URL=data[CONF_URL],
            default_CONF_API_KEY=data[CONF_API_KEY],
            default_CONF_CONFIG_VERSION_DHCP_SERVER=data[CONF_CONFIG_VERSION_DHCP_SERVER],
            default_CONF_VERIFY_SSL=data[CONF_VERIFY_SSL],
            default_CONF_TRACKER_INTERFACE=data[CONF_TRACKER_INTERFACE],
            default_CONF_DETECTION_TIME=data[CONF_DETECTION_TIME],
        )

        return self.async_show_form(
            step_id="user", data_schema=filled_data_schema, errors=errors
        )
