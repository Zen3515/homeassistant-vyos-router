"""
Serve as a simple api for VyOS, only support feature for device tracker
"""
import re
import logging
import requests  # used as fallback only

from typing import Any, Callable, Literal, Optional
from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)


class VyOSApiError(Exception):
    """General VyOS Exeption"""


class VyOSApi:
    """
    Manage VyOS api call

    # Parameters

    `api_url`: str -- example https://192.168.1.1:11443/

    `api_key`: str -- example MY-HTTPS-API-PLAINTEXT-KEY

    `verify_ssl`: bool -- whether to trust self verify certificate

    """

    PRESENCE_ARP_STATES = frozenset({"REACHABLE", "STALE", "DELAY"})
    TABLE_DELIMITER_PATTERN = re.compile("[^\s]+\s*")

    def __init__(
        self,
        websession: Optional[ClientSession],
        api_url: str,
        api_key: str,
        verify_ssl: bool = False,
    ) -> None:
        self.websession = websession
        self.api_url = api_url.strip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.allow_redirects = True

    async def make_request(
        self, path: Literal["show", "retrieve"], headers: dict, payload: dict
    ):
        """make request to VyOS api"""
        if self.websession is None:
            return requests.post(
                f"{self.api_url}/{path}",
                headers=headers,
                data=payload,
                allow_redirects=self.allow_redirects,
                verify=self.verify_ssl,
            )
        else:
            return await self.websession.post(
                f"{self.api_url}/{path}",
                headers=headers,
                data=payload,
                allow_redirects=True,
                verify_ssl=self.verify_ssl,
            )

    @classmethod
    def _parse_table(
        cls,
        table: str,
        delimiter_line_index: int = 1,
        column_names: list[str] = None,
        key: Optional[str] = None,
        filter_func: Optional[Callable[[list[str]], bool]] = None,
    ):
        """
        Process table style from vyos, missing data becomes empty string ''

        ### Example input

        ```
        IP address     Hardware address    State    Lease start          Lease expiration     Remaining    Pool    Hostname
        -------------  ------------------  -------  -------------------  -------------------  -----------  ------  -------------------------------

        Interface        IP Address                        S/L  Description
        ---------        ----------                        ---  -----------
        ```
        """
        table_lines = table.strip().splitlines()

        col_indice = [0]
        start_index = 0
        for col in cls.TABLE_DELIMITER_PATTERN.findall(
            table_lines[delimiter_line_index]
        ):
            start_index += len(col)
            col_indice.append(start_index)
        # in some case, the message is longer than delimiter line so we use absolute end for index
        col_indice.pop(-1)
        col_indice.append(None)

        def parse_line_func(line: str):
            parsed_line: list[str] = []
            for i in range(len(col_indice) - 1):
                start_index, stop_index = col_indice[i], col_indice[i + 1]
                parsed_line.append(line[start_index:stop_index].strip())
            return parsed_line

        if column_names is None:
            column_names = parse_line_func(table_lines[delimiter_line_index - 1])

        if key is None:
            return cls._parse_table_as_list(
                table_lines[delimiter_line_index + 1 :], parse_line_func, filter_func
            )
        else:
            return cls._parse_table_as_dict(
                table_lines[delimiter_line_index + 1 :],
                column_names,
                key,
                parse_line_func,
                filter_func,
            )

    @classmethod
    def _parse_table_as_list(
        cls,
        table_lines: list[str],
        parse_line_func: Callable[[str], list[str]],
        filter_func: Optional[Callable[[list[str]], bool]] = None,
    ):
        parsed_table: list[str] = []
        for line in table_lines:
            parsed_line = parse_line_func(line)
            if (filter_func is None) or (
                filter_func is not None and filter_func(parsed_line)
            ):
                parsed_table.append(parse_line_func(line))
        return parsed_table

    @classmethod
    def _parse_table_as_dict(
        cls,
        table_lines: list[str],
        column_names: list[str],
        key: str,
        parse_line_func: Callable[[str], list[str]],
        filter_func: Optional[Callable[[dict[str, str]], bool]] = None,
    ):
        parsed_table: dict[str, dict[str, str]] = {}
        for line in table_lines:
            parsed_line = {
                col_name: value
                for col_name, value in zip(column_names, parse_line_func(line))
            }
            if (filter_func is None) or (
                filter_func is not None and filter_func(parsed_line)
            ):
                parsed_table[parsed_line[key]] = parsed_line
        return parsed_table

    async def get_present_arp_clients(self, interface: list[str] = []):
        """
        API DOC:

        curl -k --location --request POST 'https://192.168.1.1:11443/show' --form data='{"op": "show", "path": ["arp"]}' --form key='MY-HTTPS-API-PLAINTEXT-KEY'

        return dict using mac address as a key and value dict
        """
        interface = frozenset(interface)
        should_check_interface = len(interface) > 0
        # or we could `show arp interface eth1``
        payload = {"data": '{"op": "show", "path": ["arp"]}', "key": self.api_key}
        headers = {}
        try:
            res = await self.make_request("show", headers=headers, payload=payload)
        except Exception as err:
            raise VyOSApiError from err
        if not res.ok:
            raise VyOSApiError(res)
        arp_table_raw: str = (await res.json(content_type=None))["data"]

        # TODO: check if we need partial function for the variables
        def filter_arp_entry(arp_entry_dict: dict[str, str]):
            # is_valid = len(arp_entry_dict["mac"]) == 17 # we don't need to check mac from arp table
            is_presence = arp_entry_dict["arp_state"] in VyOSApi.PRESENCE_ARP_STATES
            is_valid_interface = (not should_check_interface) or (arp_entry_dict["interface"] in interface)
            _LOGGER.debug(f"Filtering {arp_entry_dict}\nis_presence={is_presence},is_valid_interface={is_valid_interface}")
            return is_presence and is_valid_interface

        arp_clients: dict[
            str, dict[Literal["ip", "interface", "mac", "arp_state"], str]
        ] = self._parse_table(
            arp_table_raw,
            delimiter_line_index=1,
            column_names=["ip", "interface", "mac", "arp_state"],
            key="ip",
            filter_func=filter_arp_entry,
        )

        # arp_clients = {
        #     arp_entry[2]
        #     .lower()
        #     .strip(): {
        #         "ip": arp_entry[0],
        #         "interface": arp_entry[1],
        #         "mac": arp_entry[2],
        #         "arp_state": arp_entry[3],
        #     }
        #     for table_line in arp_table_raw.splitlines()[2:]
        #     if (
        #         (arp_entry := table_line.split())[-1].strip()
        #         in VyOSApi.PRESENCE_ARP_STATES
        #     )
        #     and ((not should_check_interface) or (arp_entry[1].strip() in interface))
        # }

        return arp_clients

    async def list_interfaces(self):
        """
        API DOC:

        curl -k --location --request POST 'https://192.168.1.1:11443/show' --form data='{"op": "show", "path": ["interfaces"]}' --form key='MY-HTTPS-API-PLAINTEXT-KEY'
        """
        payload = {
            "data": '{"op": "show", "path": ["interfaces"]}',
            "key": self.api_key,
        }
        headers = {}
        try:
            res = await self.make_request("show", headers=headers, payload=payload)
        except Exception as err:
            raise VyOSApiError from err
        if not res.ok:
            raise VyOSApiError(res)
        interfaces_summary_raw: str = (await res.json(content_type=None))["data"]

        interfaces_detail: list[list[str]] = self._parse_table(
            interfaces_summary_raw,
            delimiter_line_index=2,
            column_names=["interfaces", "ip", "s/l", "desc"],
        )

        # interfaces = [
        #     interface_line.split()[0].strip()
        #     for interface_line in interfaces_summary_raw.splitlines()[2:]
        # ]
        interfaces = [if_line[0] for if_line in interfaces_detail]
        return interfaces

    async def get_dhcp_lease(self):
        """
        API DOC:

        curl -k --location --request POST 'https://192.168.1.1:11443/show' --form data='{"op": "show", "path": ["dhcp", "server", "leases", "state", "all"]}' --form key='MY-HTTPS-API-PLAINTEXT-KEY'
        """
        payload = {
            "data": '{"op": "show", "path": ["dhcp", "server", "leases", "state", "all"]}',
            "key": self.api_key,
        }
        headers = {}
        try:
            res = await self.make_request("show", headers=headers, payload=payload)
        except Exception as err:
            raise VyOSApiError from err
        if not res.ok:
            raise VyOSApiError(res)
        lease_table_raw: str = (await res.json(content_type=None))["data"]
        lease_table: dict[
            str,
            dict[
                Literal[
                    "ip",
                    "mac",
                    "lease_state",
                    "lease_start",
                    "lease_expire",
                    "lease_remaining",
                    "pool",
                    "hostname",
                ],
                str,
            ],
        ] = self._parse_table(
            lease_table_raw,
            delimiter_line_index=1,
            column_names=[
                "ip",
                "mac",
                "lease_state",
                "lease_start",
                "lease_expire",
                "lease_remaining",
                "pool",
                "hostname",
            ],
            key="mac",
        )
        return lease_table

    async def get_config(self, paths: list[str]):
        paths_str_payload = '["' + '", "'.join(paths) + '"]'
        payload = {
            "data": f'{{"op": "showConfig", "path": {paths_str_payload}}}',
            "key": self.api_key,
        }
        headers = {}
        try:
            res = await self.make_request("retrieve", headers=headers, payload=payload)
        except Exception as err:
            raise VyOSApiError from err
        if not res.ok:
            raise VyOSApiError(res)
        raw_config: dict[str, Any] = (await res.json(content_type=None))["data"]
        return raw_config
