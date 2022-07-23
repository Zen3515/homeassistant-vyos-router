import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from typing import Final, Literal

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform

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

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
        vol.Optional(
            CONF_TRACKER_INTERFACE,
            msg="You can use comma `,` without space to specify multiple interface",
            default="",
        ): cv.string,
        vol.Optional(CONF_DETECTION_TIME, default=DEFAULT_DETECTION_TIME): int,
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
