import argparse
import asyncio
import ipaddress
import json
import os
import sys
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict, List

import meraki.aio


class SubnetPool:
    def __init__(self, network: ipaddress.IPv4Network, mask: int):
        self.network = network
        self.mask = mask
        self.usedAddresses = 0

    def __str__(self):
        return f"{self.network} mask {self.mask}"


def filter_changelog(changelog, template_id):
    result = []
    for c in changelog:
        if not "networkId" in c.keys():
            continue
        if (
            c["page"] != "Addressing & VLANs"
            or c["label"] != "Vlans Config template options"
            or c["networkId"] != template_id
        ):
            continue
        result.append(c)
    return result


def parse_vlan_config_template(options: str) -> Dict:
    """ this methos will load the new/oldValue fields into dictionaries """

    return json.loads(options.replace("=>", ":")) if options else None


def extract_ts(js):
    """ just a helper function for sorting the changelog """
    dt = datetime.strptime(js["ts"], "%Y-%m-%dT%H:%M:%S.%fZ")
    ts = dt.timestamp()
    return int(ts)


def get_template_subnet_ranges(template_id: str, changelog):
    """ this method will extract all subnets from the changelog for a given template"""
    changes = filter_changelog(changelog, template_id)
    changes.sort(key=extract_ts)
    subnets = []
    for c in changes:
        oldValue = parse_vlan_config_template(c["oldValue"])
        newValue = parse_vlan_config_template(c["newValue"])
        if oldValue or not newValue:
            if oldValue in subnets:
                subnets.remove(oldValue)
        if newValue:
            subnets.append(newValue)
    return subnets


def get_supernetworks(subnetRanges) -> List[SubnetPool]:
    superNetworks = []
    for x in subnetRanges:
        network = ipaddress.IPv4Network(x["subnetPool"])
        mask = int(x["mask"])
        addNetwork = True
        for superNetwork in superNetworks:
            if network == superNetwork.network:
                addNetwork = False
                if superNetwork.mask < mask:
                    superNetwork.mask = mask
                break
            if network.subnet_of(superNetwork.network):
                addNetwork = False
                if superNetwork.mask < mask:
                    superNetwork.mask = mask
                break
            if network.supernet_of(superNetwork.network):
                superNetwork.network = network
                if superNetwork.mask < mask:
                    superNetwork.mask = mask
                addNetwork = False
                break
        if addNetwork:
            superNetworks.append(SubnetPool(network, mask))
    return superNetworks


async def main():

    parser = argparse.ArgumentParser(
        description="Analyze the usage of subnetPool templates"
    )
    parser.add_argument(
        "-o",
        "--organization",
        type=str,
        nargs="+",
        dest="organizations",
        required=True,
        help="the name/id of the organization(s) you want to analyze",
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
        base_url="https://api-mp.meraki.com/api/v0",
        log_file_prefix=__file__[:-3],
        print_console=False,
    ) as aiomeraki:
        # Get list of organizations to which API key has access
        organizations = await aiomeraki.organizations.getOrganizations()
        for o in organizations:
            if o["id"] in args.organizations or o["name"] in args.organizations:
                print(f"Analyzing organization {o['name']}")

                # dirty hack: download the changelog to read the subnetPool ranges
                print(f"Downloading Changelog")
                changelog = await aiomeraki.change_log.getOrganizationConfigurationChanges(
                    o["id"], total_pages=-1
                )

                print("Downloading templates")
                templates = await aiomeraki.config_templates.getOrganizationConfigTemplates(
                    o["id"]
                )
                if len(templates) == 0:
                    print("Organization doesn't have any templates defined")
                    return
                subnetRanges = []
                for t in templates:
                    print(f"Analyzing template {t['name']}")
                    if "appliance" not in t["productTypes"]:
                        continue
                    subnetRanges.extend(get_template_subnet_ranges(t["id"], changelog))

                print("Getting largest supernetworks:")
                supernetworks = get_supernetworks(subnetRanges)
                subnetCounter = []
                for x in supernetworks:
                    print(x)

                networks = await aiomeraki.networks.getOrganizationNetworks(o["id"])
                vlan_tasks = []
                for n in networks:
                    if not (
                        "configTemplateId" in n.keys()
                        and "appliance" in n["productTypes"]
                    ):
                        continue
                    vlan_tasks.append(aiomeraki.vlans.getNetworkVlans(n["id"]))

                print("Downloading VLAN information")
                for task in asyncio.as_completed(vlan_tasks):
                    vlans = await task
                    for v in vlans:
                        subnet = ipaddress.IPv4Network(v["subnet"])
                        for superNetwork in supernetworks:
                            if superNetwork.network.supernet_of(subnet):
                                superNetwork.usedAddresses += subnet.num_addresses
                                break

                # print statistics
                for superNetwork in supernetworks:
                    smallest_subnet = ipaddress.IPv4Network(
                        f"{str(superNetwork.network.network_address)}/{superNetwork.mask}"
                    )
                    addresses = smallest_subnet.num_addresses
                    total_subnets = int(superNetwork.network.num_addresses / addresses)
                    used_subnets = int(superNetwork.usedAddresses / addresses)
                    free_subnets = total_subnets - used_subnets
                    print(
                        f"{superNetwork} subnetworks: total={total_subnets} used={used_subnets} free={free_subnets} -> usage {100*used_subnets/total_subnets}%"
                    )

        print("Script complete!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
