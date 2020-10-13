import argparse
import asyncio
import json
import os
import sys
import qrcode

import meraki.aio


def wifi_code(
    ssid: str, hidden: bool, authentication_type: str, password: str = None
) -> str:
    """Generate a wifi code for the given parameters"""
    hidden = "true" if hidden else "false"
    authentication_type = authentication_type.upper()
    if authentication_type in ("WPA", "WEP"):
        return f"WIFI:T:{authentication_type};S:{ssid};P:{password};H:{hidden};;"

    elif authentication_type == "OPEN":
        return f"WIFI:T:nopass;S:{ssid};H:{hidden};;"


async def get_ssid_settings(
    aiomeraki: meraki.aio.AsyncDashboardAPI,
    network_id: str,
    network_name: str,
    ssids: str,
):
    network_ssids = await aiomeraki.wireless.getNetworkWirelessSsids(network_id)
    for network_ssid in network_ssids:
        if network_ssid["name"].startswith("Unconfigured"):
            continue
        if ssids and network_ssid["name"] not in ssids:
            continue
        auth_mode = network_ssid["authMode"]
        if auth_mode not in ("open", "psk"):
            print(f"{auth_mode} is currently not supported by this script.")
            continue
        encryptionMode = network_ssid.get("encryptionMode", "open")
        password = network_ssid.get("psk", None)
        hidden = not network_ssid["visible"]
        ssid = network_ssid["name"]
        print(f"Generating image for {network_name}-{ssid}")
        code = wifi_code(ssid, hidden, encryptionMode, password)
        img = qrcode.make(code)
        img.save(f"./img/{network_name}_{ssid}.png")


async def main():

    parser = argparse.ArgumentParser(
        description="Generates QRCodes from Meraki wireless networks"
    )
    parser.add_argument(
        "-o",
        "--organization",
        type=str,
        dest="organization",
        required=False,
        help="the name/id of the organization",
    )

    parser.add_argument(
        "-n",
        "--network",
        type=str,
        dest="networks",
        nargs="+",
        required=False,
        help="the name/id of the networks to generate the qr codes from. If you are providing this parameter, then you must provide the organization.",
    )

    parser.add_argument(
        "-s",
        "--ssid",
        type=str,
        dest="ssids",
        nargs="+",
        required=False,
        help="the name of the ssids to generate the qr codes",
    )

    if len(sys.argv) < 2:
        parser.print_help()
        return

    try:
        args = parser.parse_args()
    except SystemExit:
        return
    except:
        print("could not parse arguments")
        parser.print_help()
        return

    # Instantiate a Meraki dashboard API session
    # NOTE: you have to use "async with" so that the session will be closed correctly at the end of the usage
    async with meraki.aio.AsyncDashboardAPI(
        api_key=None,
        base_url="https://api.meraki.com/api/v1",
        log_file_prefix=__file__[:-3],
        print_console=False,
        maximum_retries=5,
    ) as aiomeraki:
        # Get list of organizations to which API key has access

        # getting network ids
        networks = []
        if args.organization:
            organizations = await aiomeraki.organizations.getOrganizations()
            for o in organizations:
                if o["id"] == args.organization or o["name"] == args.organization:
                    o_networks = await aiomeraki.organizations.getOrganizationNetworks(
                        o["id"]
                    )
                    for n in o_networks:
                        if args.networks:
                            if n["id"] in args.networks or n["name"] in args.networks:
                                networks.append(n["id"])
                        else:  # no networks given -> use all of the organization
                            networks.append(n["id"])
        else:
            if not args.networks:
                print("You have to provide either organization or network ids")
                parser.print_help()
                return
            networks = args.networks

        networIdNameMap = {}

        print("Getting Network Data")
        network_tasks = [aiomeraki.networks.getNetwork(n) for n in networks]
        for task in asyncio.as_completed(network_tasks):
            network = await task
            if "wireless" not in network["productTypes"]:
                print(
                    f"{network['name']}({network['id']}) doesn't have a wireless device"
                )
                continue
            networIdNameMap[network["id"]] = network["name"]

        if not os.path.exists("./img/"):
            os.makedirs("./img/")

        ssid_tasks = [
            get_ssid_settings(aiomeraki, id, name, args.ssids)
            for id, name in networIdNameMap.items()
        ]
        for task in asyncio.as_completed(ssid_tasks):
            ssid = await task
        print("Script complete!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
