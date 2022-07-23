"""Device tracker support for VyOS routers."""
from __future__ import annotations

from .const import (
    DOMAIN,
    KEY_COORDINATOR,
)
from .router import VyOSApiDataUpdateCoordinator, VyOSDevice

from typing import Any, Optional
from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER,
    SOURCE_TYPE_ROUTER,
)
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry

# BELOW ARE DEPRICATED

# async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> DeviceScanner:
#     """Configure the OPNSense device_tracker."""
#     interface_client = hass.data[OPNSENSE_DATA]["interfaces"]
#     scanner = OPNSenseDeviceScanner(
#         interface_client, hass.data[OPNSENSE_DATA][CONF_TRACKER_INTERFACE]
#     )
#     return scanner


# class OPNSenseDeviceScanner(DeviceScanner):
#     """This class queries a router running OPNsense."""

#     def __init__(self, client, interfaces):
#         """Initialize the scanner."""
#         self.last_results = {}
#         self.client = client
#         self.interfaces = interfaces

#     def _get_mac_addrs(self, devices):
#         """Create dict with mac address keys from list of devices."""
#         out_devices = {}
#         for device in devices:
#             if not self.interfaces:
#                 out_devices[device["mac"]] = device
#             elif device["intf_description"] in self.interfaces:
#                 out_devices[device["mac"]] = device
#         return out_devices

#     def scan_devices(self):
#         """Scan for new devices and return a list with found device IDs."""
#         self.update_info()
#         return list(self.last_results)

#     def get_device_name(self, device):
#         """Return the name of the given device or None if we don't know."""
#         if device not in self.last_results:
#             return None
#         hostname = self.last_results[device].get("hostname") or None
#         return hostname

#     def update_info(self):
#         """Ensure the information from the OPNSense router is up to date.

#         Return boolean if scanning successful.
#         """

#         devices = self.client.get_arp()
#         self.last_results = self._get_mac_addrs(devices)

#     def get_extra_attributes(self, device):
#         """Return the extra attrs of the given device."""
#         if device not in self.last_results:
#             return None
#         if not (mfg := self.last_results[device].get("manufacturer")):
#             return {}
#         return {"manufacturer": mfg}

# ABOVE ARE DEPRICATED

# DEFAULT_DEVICE_NAME = "Unknown device"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for VyOS component."""
    coordinator: VyOSApiDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ][KEY_COORDINATOR]
    # vyos_api = hass.data[DOMAIN][config_entry.entry_id][VYOS_API]
    # tracker_interfaces = hass.data[DOMAIN][config_entry.entry_id][CONF_TRACKER_INTERFACE]
    # update_listener only use for reload config_entry, so, not use here
    # update_listener = hass.data[DOMAIN][config_entry.entry_id][UPDATE_LISTENER]
    tracked: dict[str, VyOSApiDataUpdateCoordinatorTracker] = {}

    registry = entity_registry.async_get(hass)

    # Restore clients that is not a part of active clients list.
    for entity in registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.domain == DEVICE_TRACKER
        ):

            if (
                entity.unique_id in coordinator.vyos_data.devices
                or entity.unique_id not in coordinator.vyos_data.all_devices
            ):
                continue
            coordinator.vyos_data.restore_device(entity.unique_id)

    @callback
    def update_router() -> None:
        """Update the status of the device."""
        update_items(coordinator, async_add_entities, tracked)

    config_entry.async_on_unload(coordinator.async_add_listener(update_router))

    update_router()


@callback
def update_items(
    coordinator: VyOSApiDataUpdateCoordinator,
    async_add_entities: AddEntitiesCallback,
    tracked: dict[str, VyOSApiDataUpdateCoordinatorTracker],
):
    """Update tracked device state from the hub."""
    new_tracked: list[VyOSApiDataUpdateCoordinatorTracker] = []
    for mac, device in coordinator.vyos_data.devices.items():
        if mac not in tracked:
            tracked[mac] = VyOSApiDataUpdateCoordinatorTracker(device, coordinator)
            new_tracked.append(tracked[mac])

    if new_tracked:
        async_add_entities(new_tracked)


# @callback
# async def add_entities(
#     vyos_api: VyOSApi,
#     tracker_interfaces: list[str],
#     async_add_entities: AddEntitiesCallback,
#     tracked: set[str],
# ) -> None:
#     """Add new tracker entities from the router."""
#     new_tracked = []

#     arp_clients = await vyos_api.get_arp_clients(tracker_interfaces)

#     for ip, interface, mac, state in arp_clients:
#         if mac in tracked:
#             continue

#         new_tracked.append(VyOSDevice(ip, interface, mac, state))
#         tracked.add(mac)

#     if new_tracked:
#         async_add_entities(new_tracked)


class VyOSApiDataUpdateCoordinatorTracker(
    CoordinatorEntity[VyOSApiDataUpdateCoordinator], ScannerEntity
):
    """Representation of a VyOS device."""

    def __init__(
        self, device: VyOSDevice, coordinator: VyOSApiDataUpdateCoordinator
    ) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = str(device.name)
        self._attr_unique_id = device.mac

    @property
    def is_connected(self) -> bool:
        """Return true if the client is connected to the network."""
        if (
            self.device.last_seen
            and (dt_util.utcnow() - self.device.last_seen)
            < self.coordinator.option_detection_time
        ):
            return True
        return False

    @property
    def source_type(self) -> str:
        """Return the source type of the client."""
        return SOURCE_TYPE_ROUTER

    @property
    def hostname(self) -> str:
        """Return the hostname of the client."""
        return self.device.name

    @property
    def mac_address(self) -> str:
        """Return the mac address of the client."""
        return self.device.mac

    @property
    def ip_address(self) -> str:
        """Return the mac address of the client."""
        return self.device.ip_address

    @property
    def extra_state_attributes(self) -> Optional[dict[str, Any]]:
        """Return the device state attributes."""
        return self.device.attrs if self.is_connected else None
