import argparse
import asyncio
import aiodns
import json
import os
import sys
import secrets
import string
import logging

from typing import List,Dict

from meraki.aio import AsyncDashboardAPI

dns_resolver = aiodns.DNSResolver()
logger = logging.getLogger(__name__)

class VPNOrganization():
    def __init__(self, organizationID:str, vpn_networks:List[VPNNetwork],vpn_peers:Dict,tags:List[str]):
        self.organizationID = organizationID
        self.vpn_networks = vpn_networks
        self.vpn_peers = vpn_peers
        self.tags = tags

class VPNNetwork:
    def __init__(self, fqdn: str, publicIP: str, networks: List[str]):
        self.fqdn = fqdn
        self.publicIP = publicIP
        self.networks = networks


async def get_vpn_networks(
    aiomeraki: AsyncDashboardAPI, organizationID: str, tags: List[str] = []
) -> List[VPNNetwork]:

    task_o_networks = aiomeraki.organizations.getOrganizationNetworks(
        organizationID, tags=tags, tagsFilterType="withAnyTags"
    )

    task_o_devices = aiomeraki.organizations.getOrganizationDevicesStatuses(
        organizationID
    )

    o_networks, o_devices = await asyncio.gather(task_o_networks, task_o_devices)

    ret = []
    for n in o_networks:
        n_devices = await aiomeraki.networks.getNetworkDevices(n["id"])
        for d in n_devices:
            if d["model"][0:2] != "MX":
                continue
            publicIP = None
            for o_d in o_devices:
                if o_d["serial"] == d["serial"]:
                    publicIP = o_d["publicIp"]
                    break
            if not publicIP:
                logger.warn(f"Skipping {d['serial']} - no public IP available")
            mmi = await aiomeraki.devices.getDeviceManagementInterface(d["serial"])
            fqdn = mmi["ddnsHostnames"]["activeDdnsHostname"]

            site2siteVPN = await aiomeraki.appliance.getNetworkApplianceVpnSiteToSiteVpn(
                n["id"]
            )
            subnets = []
            for s in site2siteVPN["subnets"]:
                if s["useVpn"]:
                    subnets.append(s["localSubnet"])
            ret.append(VPNNetwork(fqdn, publicIP, subnets))
            break  # there is only one appliance per network, so we can skip the other devices

    return ret


async def main():

    parser = argparse.ArgumentParser(
        description="This script will create/update the VPN connection between two meraki organizations"
    )
    parser.add_argument(
        "-o1",
        "--organization1",
        type=str,
        dest="organization1",
        required=True,
        help="the name/id of the first organization",
    )
    parser.add_argument(
        "-o2",
        "--organization2",
        type=str,
        dest="organization2",
        required=True,
        help="the name/id of the second organization",
    )

    parser.add_argument(
        "-t1",
        "--tags1",
        type=str,
        dest="tags1",
        nargs="+",
        default=[],
        required=False,
        help="the tags from the first organization to grab the vpn networks and remote IPs. Leave Empty for all",
    )

    parser.add_argument(
        "-t2",
        "--tags2",
        type=str,
        dest="tags2",
        nargs="+",
        default=[],
        required=False,
        help="the tags from the second organization to grab the vpn networks and remote IPs. Leave Empty for all",
    )

    parser.add_argument(
        "-p",
        "--psk",
        type=str,
        dest="psk",
        required=False,
        help='the psk for the vpn connection. Use "random" to generate a random key',
    )

    parser.add_argument(
        "--ike-version",
        type=int,
        dest="ike_version",
        required=False,
        help="the IKE version. Must be 1 or 2",
    )

    if len(sys.argv) < 3:
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

    if args.psk == "random":
        alphabet = string.ascii_letters + string.digits + '_-,.!"§$%&/()='
        args.psk = "".join(secrets.choice(alphabet) for i in range(30))

    # Instantiate a Meraki dashboard API session
    # NOTE: you have to use "async with" so that the session will be closed correctly at the end of the usage
    async with AsyncDashboardAPI(
        api_key=None,
        base_url="https://api.meraki.com/api/v1",
        log_file_prefix=__file__[:-3],
        print_console=True,
        maximum_retries=5,
    ) as aiomeraki:
        # Get list of organizations to which API key has access

        organizations = await aiomeraki.organizations.getOrganizations()

        vpn_orgs = []
        for o in organizations:
            if o["id"] == args.organization1 or o["name"] == args.organization1:
                networks = await get_vpn_networks(
                    aiomeraki, o["id"], args.tags1
                )

                peers = await aiomeraki.appliance.getOrganizationApplianceVpnThirdPartyVPNPeers(o["id"])
                org = VPNOrganization(o["id"], networks, peers, args.tags1)
                vpn_orgs.append(org)
            elif o["id"] == args.organization2 or o["name"] == args.organization2:
                networks = await get_vpn_networks(
                    aiomeraki, o["id"], args.tags2
                )

                peers = await aiomeraki.appliance.getOrganizationApplianceVpnThirdPartyVPNPeers(o["id"])
                org = VPNOrganization(o["id"], networks, peers, args.tags2)
                vpn_orgs.append(org)

        if len(vpn_orgs) != 2:
            logger.error("Could not find the correct organizations")
            return
        
        print("Script complete!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
