# homeassistant-vyos-router

`VyOS Rounter` is a custom integration for Homeassistant which provides `Presence detection` as `device_tracker` functionality for VyOS Router. This integration uses direct [HTTP-API](https://docs.vyos.io/en/latest/configuration/service/https.html) from VyOS Router.

To use this integration you need to enable [HTTP-API](https://docs.vyos.io/en/latest/configuration/service/https.html) on your VyOS Router.

## Installation

First enable [HTTP-API](https://docs.vyos.io/en/latest/configuration/service/https.html) on your VyOS Router.

### HACS

Add this repository to your HACS installation, then install.

### Manual

Download stable release contents from `custom_components/vyos`, then copy to your home assistant at `/config/custom_components/vyos`.

Once the integration is installed be sure to restart hass and hard-refresh the UI in the browser (ctrl-F5) if it doesn't appear in the list.

## Usage

After `VyOS Router` is installed, you can add your device from Home Assistant UI.

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=vyos)

To connect to the device you need to provide the following data:

- **url** this include `https://` protocal and port number `:port`, for instance `https://192.168.1.1:11123`
- **api_key** the key that you set from VyOS doc `MY-HTTPS-API-PLAINTEXT-KEY`
- **verify_ssl** whether to use an SSL connection
- **tracker_interfaces** this is optional, you can use comma `,` to specify multiple interface, for example `eth0,eth1,wlan0`. If you leave it empty, it'll use all interfaces.
- **detection_time** How long before consider at away or home in seconds.

After configured the integration, the device entities will be disabled by default. Find the required mac addresses using the disabled entity list, then activate them as needed.

## Support

### Issues and Pull requests

If you have discovered a problem with the integration or simply want to request a new feature, please create a new issue.

You may also submit pull requests to the repository.
