import argparse
import asyncio
import json
import os
import re
import sys

from meraki.aio import AsyncDashboardAPI


async def find_in_networks(
    aiomeraki: AsyncDashboardAPI, network, pattern, options: str
):
    ret = {
        "name": network["name"],
        "id": network["id"],
        "match": False,
        "devices": [],
        "clients": [],
        "bluetooth_clients": [],
    }

    # these 3 calls could run concurrently
    if "d" in options:
        devices = await aiomeraki.networks.getNetworkDevices(network["id"])
        for d in devices:
            if "name" not in d.keys():
                d["name"] = d["mac"]
            name = d["name"]
            if name and pattern.match(name):
                ret["devices"].append(d)

    if "c" in options:
        clients = await aiomeraki.networks.getNetworkClients(
            network["id"], total_pages="all"
        )
        for c in clients:
            if "description" not in c.keys():
                c["description"] = c["mac"]
            description = c["description"]
            mac = c["mac"]
            ip = c["ip"]
            ip6 = c["ip6"]
            if (
                (description and pattern.match(description))
                or (mac and pattern.match(mac))
                or (ip and pattern.match(ip))
                or (ip6 and pattern.match(ip6))
            ):
                ret["clients"].append(c)

    if "b" in options and "wireless" in network["productTypes"]:
        bluetooth_clients = await aiomeraki.networks.getNetworkBluetoothClients(
            network["id"], total_pages="all"
        )
        for b in bluetooth_clients:
            if "name" not in b.keys():
                b["name"] = b["mac"]
            if "deviceName" not in b.keys():
                b["deviceName"] = b["mac"]

            name = b["name"]
            deviceName = b["deviceName"]

            if (name and pattern.match(name)) or (
                deviceName and pattern.match(deviceName)
            ):
                ret["bluetooth_clients"].append(b)

    if (
        ("n" in options and pattern.match(network["name"]))
        or ret["clients"]
        or ret["devices"]
        or ret["bluetooth_clients"]
    ):
        ret["match"] = True

    return ret


async def find_in_organization(
    aiomeraki: AsyncDashboardAPI, organization, pattern, filter_networks, options: str
):
    networks = await aiomeraki.organizations.getOrganizationNetworks(
        organization["id"], total_pages="all"
    )
    if filter_networks:
        networks = [
            n
            for n in networks
            if n["id"] in filter_networks or n["name"] in filter_networks
        ]
        options = options.replace("n", "")
    network_tasks = [find_in_networks(aiomeraki, o, pattern, options) for o in networks]

    ret = {
        "name": organization["name"],
        "id": organization["id"],
        "match": False,
        "networks": [],
    }

    for task in asyncio.as_completed(network_tasks):
        result = await task
        if result["match"]:
            ret["networks"].append(result)

    if ("o" in options and pattern.match(organization["name"])) or ret["networks"]:
        ret["match"] = True

    return ret


async def main():

    parser = argparse.ArgumentParser(
        description="This scripts helps to find the id of an organization, network, device or (bluetooth) client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        dest="pattern",
        required=True,
        help="the regular expression to search for",
    )

    parser.add_argument(
        "-s",
        "--search_options",
        type=str,
        dest="options",
        required=False,
        default="ond",
        help="specifies which objects should be looked up: o=organizations, n=networks, d=devices, c=clients, b=bluetooth clients",
    )

    parser.add_argument(
        "-o",
        "--organization",
        type=str,
        dest="organization",
        nargs="+",
        required=False,
        help="The name/id of the organizations under which you want to limit the search. This makes the o option of -s obsolete.",
    )

    parser.add_argument(
        "-n",
        "--network",
        type=str,
        dest="networks",
        nargs="+",
        required=False,
        help="the name/id of the networks under which you want to limit the search. This makes the n option of -s obsolete.",
    )

    try:
        args = parser.parse_args()
    except SystemExit:
        return
    except:
        print("could not parse arguments")
        parser.print_help()
        return

    pattern = re.compile(args.pattern)
    options = args.options.lower()

    # Instantiate a Meraki dashboard API session
    # NOTE: you have to use "async with" so that the session will be closed correctly at the end of the usage
    async with AsyncDashboardAPI(
        api_key=None,
        base_url="https://api.meraki.com/api/v1",
        log_file_prefix=__file__[:-3],
        print_console=False,
        maximum_retries=5,
    ) as aiomeraki:
        # Get list of organizations to which API key has access

        print(f"Searching for pattern {pattern}")
        organizations = await aiomeraki.organizations.getOrganizations()
        if args.organization:
            organizations = [
                o
                for o in organizations
                if o["id"] in args.organization or o["name"] in args.organization
            ]
            options = options.replace("o", "")

        organization_tasks = [
            find_in_organization(aiomeraki, o, pattern, args.networks, options)
            for o in organizations
        ]
        counter = 1
        task_count = len(organization_tasks)

        for task in asyncio.as_completed(organization_tasks):
            result = await task
            if result["match"]:
                print(f"Organization \"{result['name']}\" - {result['id']}")
                for n in result["networks"]:
                    print(f"\t\tNetwork \"{n['name']}\" - {n['id']}")

                    if n["devices"]:
                        print(f"\t\tDevices: <Name> - <Serial>")
                        for d in n["devices"]:
                            print(f"\t\t\t\"{d['name']}\" - {d['serial']}")

                    if n["clients"]:
                        print(
                            f"\t\tClients: <Description> - <ID> - <MAC> - <IP> - <IPv6>"
                        )
                        for d in n["clients"]:
                            print(
                                f"\t\t\t\"{d['description']}\" - {d['id']} - {d['mac']} - {d['ip']} - {d['ip6']}"
                            )

                    if n["bluetooth_clients"]:
                        print(
                            f"\t\tBluetooth Clients: <DeviceName> - <Name> - <ID> - <MAC>"
                        )
                        for d in n["bluetooth_clients"]:
                            print(
                                f"\t\t\t\"{d['deviceName']}\" - \"{d['name']}\" - {d['id']} - {d['mac']}"
                            )

            print(f"Finished {counter} of {task_count} Organizations")
            counter = counter + 1

        print("Script complete!")


if __name__ == "__main__":
    asyncio.run(main())
