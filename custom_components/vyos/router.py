import logging

from .util import deep_update
from .const import (
    ATTR_DEVICE_TRACKER,
    CONF_URL,
    CONF_DETECTION_TIME,
    CONF_TRACKER_INTERFACE,
    DEFAULT_DETECTION_TIME,
    VyOSDeviceDataType,
)
from .vyosapi import VyOSApi

from typing import Any, Literal, Optional, Union
from datetime import datetime, timedelta
from functools import reduce

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util, slugify
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


_LOGGER = logging.getLogger(__name__)


class VyOSDevice:
    """Represents a network device."""

    def __init__(self, mac: str, params: VyOSDeviceDataType) -> None:
        """Initialize the network device."""
        self._mac = mac
        self._params = params
        self._last_seen: Optional[datetime] = None
        self._attrs: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return device name."""
        return self._params.get("hostname", slugify(self.mac))

    @property
    def ip_address(self) -> str:
        """Return device primary ip address."""
        return self._params["ip"]

    @property
    def mac(self) -> str:
        """Return device mac."""
        return self._mac

    @property
    def last_seen(self) -> Optional[datetime]:
        """Return device last seen."""
        return self._last_seen

    @property
    def attrs(self) -> dict[str, Any]:
        """Return device attributes."""
        attr_data = self._params
        for attr in ATTR_DEVICE_TRACKER:
            if attr in attr_data:
                self._attrs[slugify(attr)] = attr_data[attr]

    def update(
        self,
        params: Optional[VyOSDeviceDataType] = None,
        active: bool = False,
    ) -> None:
        """Update Device params."""
        if params is not None:
            self._params = params
        if active:
            self._last_seen = dt_util.utcnow()
        return self._attrs


class VyOSData:
    """Handle all communication with the VyOS API."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: VyOSApi
    ) -> None:
        """Initialize the VyOS Client."""
        self.hass = hass
        self.config_entry = config_entry
        self.api = api
        conf = config_entry.data
        self.tracker_interfaces: list[str] = [
            iface.strip() for iface in conf[CONF_TRACKER_INTERFACE].split(",")
        ]
        self.all_devices: dict[str, VyOSDeviceDataType] = {}
        self.devices: dict[str, VyOSDevice] = {}

    @staticmethod
    def load_mac(devices: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Load dictionary using MAC address as key."""
        mac_devices = {}
        for device in devices:
            if "mac-address" in device:
                mac = device["mac-address"]
                mac_devices[mac] = device
        return mac_devices

    def restore_device(self, mac: str) -> None:
        """Restore a missing device after restart."""
        device_data = self.all_devices[mac]
        self.devices[mac] = VyOSDevice(mac, device_data)

    async def update_devices(self) -> None:
        """Get list of devices with latest status."""
        # get from static mapping to get the hostname and mac
        # get from dhcp lease to get the hostname
        # get from arp table to know the one that is online
        static_mapping_co_routine = self.api.get_config(
            ["service", "dhcp-server", "shared-network-name"]
        )
        dhcp_lease_co_routine = self.api.get_dhcp_lease()
        arp_table_co_routine = self.api.get_present_arp_clients(self.tracker_interfaces)

        static_mapping_host_detail: dict[
            str, dict[Literal["mac", "ip", "hostname"], str]
        ] = {}

        shared_network_name_dict: dict[str, dict[str, Any]]
        subnet_dict: dict[str, dict[str, Any]]
        mapping_detail: dict[
            Literal["ip-address", "mac-address", "static-mapping-parameters"],
            Union[str, list[str]],
        ]
        # shared_network_name = Lan
        # subnet_name = 192.168.1.0/24
        for _shared_network_name, shared_network_name_dict in (
            await static_mapping_co_routine
        )["shared-network-name"].items():
            for _subnet_name, subnet_dict in shared_network_name_dict["subnet"].items():
                for hostname, mapping_detail in subnet_dict["static-mapping"].items():
                    if "mac-address" not in mapping_detail:
                        continue
                    ip = mapping_detail.get("ip-address", None)
                    mac = mapping_detail["mac-address"]
                    static_mapping_host_detail[mac] = {
                        "mac": mac,
                        "ip": ip,
                        "hostname": hostname,
                    }

        self.all_devices = reduce(
            deep_update,
            (
                static_mapping_host_detail,
                (await dhcp_lease_co_routine),
                (await arp_table_co_routine),
            ),
        )
        device_list = self.all_devices

        for mac, params in device_list.items():
            if mac not in self.devices:
                self.devices[mac] = VyOSDevice(mac, self.all_devices.get(mac, {}))
            else:
                self.devices[mac].update(params=self.all_devices.get(mac, {}))
            is_active = params.get("arp_state", None) in VyOSApi.PRESENCE_ARP_STATES
            self.devices[mac].update(active=is_active)


class VyOSApiDataUpdateCoordinator(DataUpdateCoordinator):
    """VyOSApi Router Object."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: VyOSApi
    ) -> None:
        """Initialize the VyOSApi Client."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self.api = api
        self.vyos_data = VyOSData(hass, config_entry, api)
        conf = config_entry.data
        super().__init__(
            self.hass,
            _LOGGER,
            name=f"VyOS - {conf[CONF_URL]}",
            update_interval=timedelta(seconds=10),
        )

    @property
    def option_detection_time(self) -> timedelta:
        """Config entry option defining number of seconds from last seen to away."""
        return timedelta(
            seconds=self.config_entry.options.get(
                CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME
            )
        )

    async def _async_update_data(self) -> None:
        """Update VyOSApi devices information."""
        # await self.hass.async_add_executor_job(self.vyos_data.update_devices)
        await self.vyos_data.update_devices()
