import csv
from datetime import datetime, timedelta
import os
import asyncio
import argparse
import ipaddress
from typing import Dict, List
import sys

import meraki.aio

# Either input your API key below, or set an environment variable
# for example, in Terminal on macOS:  export MERAKI_DASHBOARD_API_KEY=66839003d2861bc302b292eb66d3b247709f2d0d
api_key = ""


async def createNetwork(aiomeraki, orgNr):
    org = await aiomeraki.organizations.createOrganization(name=f"TestOrg_{orgNr}")
    print(f"{orgNr} Creating Org {org['id']}")
    for y in range(10):
        n = await aiomeraki.networks.createOrganizationNetwork(
            org["id"], f"Network_{y}", "appliance switch wireless"
        )
        print(f" {orgNr} {y} Creating Network {n['id']}")


async def main():
    # Instantiate a Meraki dashboard API session
    # NOTE: you have to use "async with" so that the session will be closed correctly at the end of the usage
    async with meraki.aio.AsyncDashboardAPI(
        api_key,
        base_url="https://api.meraki.com/api/v0",
        log_file_prefix=__file__[:-3],
        print_console=False,
        maximum_concurrent_requests=5,
    ) as aiomeraki:
        gather = [createNetwork(aiomeraki, x) for x in range(200)]
        # Get list of organizations to which API key has access
        await asyncio.gather(*gather)

        print("Script complete!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
