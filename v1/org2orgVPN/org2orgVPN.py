import argparse
import asyncio
import json
import os
import sys
import secrets
import string
import logging

from typing import List, Dict

from meraki.aio import AsyncDashboardAPI

logger = logging.getLogger(__name__)


class VPNNetwork:
    def __init__(self, fqdn: str, publicIP: str, networks: List[str]):
        self.fqdn = fqdn
        self.publicIP = publicIP
        self.networks = networks


class VPNOrganization:
    def __init__(
        self,
        organizationID: str,
        vpn_networks: List[VPNNetwork],
        vpn_peers: Dict,
        tags: List[str],
    ):
        self.organizationID = organizationID
        self.vpn_networks = vpn_networks
        self.vpn_peers = vpn_peers
        self.tags = tags


class NoPSKError(Exception):
    pass


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


def prepare_vpn_peer(
    name: str,
    publicIp: str,
    privateSubnets: List[str],
    secret: str,
    ikeVersion: int,
    networkTags: List[str],
):
    return {
        "name": name[:32],
        "publicIp": publicIp,
        "privateSubnets": privateSubnets,
        "secret": secret,
        "ikeVersion": ikeVersion,
        "ipsecPoliciesPreset": "default",
        "networkTags": networkTags,
    }


async def connect_organization(
    aiomeraki: AsyncDashboardAPI,
    org1: VPNOrganization,
    org2: VPNOrganization,
    psk: str = None,
    ike_version: int = None,
):
    privateSubnets = []
    [privateSubnets.extend(x.networks) for x in org2.vpn_networks]
    new_vpn_peers = []
    for vpn_peer in org1.vpn_peers:
        for n2 in org2.vpn_networks:  # check if a peer must be updated
            if vpn_peer["name"] == n2.fqdn or vpn_peer["publicIp"] == n2.publicIP:
                vpn_peer["privateSubnets"] = privateSubnets
                if psk:
                    vpn_peer["secret"] = psk
                if ike_version:
                    vpn_peer["ikeVersion"] = ike_version

                peer = prepare_vpn_peer(
                    n2.fqdn,
                    n2.publicIP,
                    privateSubnets,
                    vpn_peer["secret"],
                    vpn_peer["ikeVersion"],
                    org1.tags if len(org1.tags) > 0 else ["all"],
                )

                new_vpn_peers.append(peer)
                break
        else:
            new_vpn_peers.append(vpn_peer)  # adding existing peers
            pass
    # adding new peers
    for n2 in org2.vpn_networks:  # check if a peer must be updated
        for vpn_peer in org1.vpn_peers:
            if vpn_peer["name"] == n2.fqdn or vpn_peer["publicIp"] == n2.publicIP:
                break
        else:
            if not psk:
                raise NoPSKError()
            peer = prepare_vpn_peer(
                n2.fqdn,
                n2.publicIP,
                privateSubnets,
                psk,
                ike_version if ike_version else 1,
                org1.tags if len(org1.tags) > 0 else ["all"],
            )
            new_vpn_peers.append(peer)

    await aiomeraki.appliance.updateOrganizationApplianceVpnThirdPartyVPNPeers(
        org1.organizationID, new_vpn_peers
    )


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
        
        logger.info("Downloading Settings")
        vpn_orgs = [None, None]
        for o in organizations:
            if o["id"] == args.organization1 or o["name"] == args.organization1:
                networks = await get_vpn_networks(aiomeraki, o["id"], args.tags1)

                peers = await aiomeraki.appliance.getOrganizationApplianceVpnThirdPartyVPNPeers(
                    o["id"]
                )
                org = VPNOrganization(o["id"], networks, peers["peers"], args.tags1)
                vpn_orgs[0] = org
            elif o["id"] == args.organization2 or o["name"] == args.organization2:
                networks = await get_vpn_networks(aiomeraki, o["id"], args.tags2)

                peers = await aiomeraki.appliance.getOrganizationApplianceVpnThirdPartyVPNPeers(
                    o["id"]
                )
                org = VPNOrganization(o["id"], networks, peers["peers"], args.tags2)
                vpn_orgs[1] = org

        if None in vpn_orgs:
            logger.error("Could not find the correct organizations")
            return
        try:
            logger.info("Updating VPN Settings")
            await connect_organization(
                aiomeraki, vpn_orgs[0], vpn_orgs[1], args.psk, args.ike_version
            )
            await connect_organization(
                aiomeraki, vpn_orgs[1], vpn_orgs[0], args.psk, args.ike_version
            )
        except NoPSKError:
            logger.error("Unable to add new peer. Please specify --psk.")


if __name__ == "__main__":
    asyncio.run(main())
