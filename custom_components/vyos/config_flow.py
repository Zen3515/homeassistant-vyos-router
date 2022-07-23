"""Config flow for VyOS integration."""

import logging
import voluptuous as vol

from .const import (
    CONF_DETECTION_TIME,
    DATA_SCHEMA,
    DOMAIN,
    CONF_TRACKER_INTERFACE,
    CONF_URL,
    CONF_API_KEY,
    CONF_VERIFY_SSL,
)
from .vyosapi import VyOSApi, VyOSApiError

from homeassistant import config_entries, core
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
        CONF_VERIFY_SSL: verify_ssl,
        CONF_TRACKER_INTERFACE: tracker_interfaces_input,
        CONF_DETECTION_TIME: detection_time,
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JuiceNet."""

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
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input):
        """Handle import."""
        return await self.async_step_user(user_input)
