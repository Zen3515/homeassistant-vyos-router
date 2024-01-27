import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from typing import Final, Literal

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform

ENTRIES_VERSION = 2

CONF_CONFIG_VERSION_DHCP_SERVER: Final = "version_dhcp_server"
# From version 8+ dhcp-server config path changed, the value obtained from `cat /config/config.boot | grep -Eo 'dhcp-server@[0-9]{1,3}'`
DEFAULT_CONFIG_VERSION_DHCP_SERVER: Final = 7
CONF_TRACKER_INTERFACE: Final = "tracker_interfaces"
CONF_DETECTION_TIME: Final = "detection_time"
DEFAULT_DETECTION_TIME: Final = 300
ATTR_DEVICE_TRACKER = {
    "lease_state",
    "lease_start",
    "lease_expire",
    "lease_remaining",
    "pool",
    "hostname",
    "interface",
    "arp_state",
}

KEY_COORDINATOR = "coordinator"

UPDATE_LISTENER: Final = "update_listener"

VYOS_API: Final = "vyos_api"

DOMAIN: Final = "vyos"

PLATFORMS = [Platform.DEVICE_TRACKER]


def get_data_schema(
        default_CONF_URL: str = None,
        default_CONF_API_KEY: str = None,
        default_CONF_CONFIG_VERSION_DHCP_SERVER: int = DEFAULT_CONFIG_VERSION_DHCP_SERVER,
        default_CONF_VERIFY_SSL: bool = False,
        default_CONF_TRACKER_INTERFACE: str = "",
        default_CONF_DETECTION_TIME: int = DEFAULT_DETECTION_TIME,
):
    return vol.Schema(
        {
            vol.Required(CONF_URL, default=default_CONF_URL): cv.string,
            vol.Required(CONF_API_KEY, default=default_CONF_API_KEY): cv.string,
            vol.Required(CONF_CONFIG_VERSION_DHCP_SERVER, default=default_CONF_CONFIG_VERSION_DHCP_SERVER): int,
            vol.Optional(CONF_VERIFY_SSL, default=default_CONF_VERIFY_SSL): cv.boolean,
            vol.Optional(
                CONF_TRACKER_INTERFACE,
                msg="You can use comma `,` without space to specify multiple interface",
                default=default_CONF_TRACKER_INTERFACE,
            ): cv.string,
            vol.Optional(CONF_DETECTION_TIME, default=default_CONF_DETECTION_TIME): int,
        }
    )


VyOSDeviceDataType = dict[
    Literal[
        "ip",
        "mac",
        "lease_state",
        "lease_start",
        "lease_expire",
        "lease_remaining",
        "pool",
        "hostname",
        "interface",
        "arp_state",
    ],
    str,
]
