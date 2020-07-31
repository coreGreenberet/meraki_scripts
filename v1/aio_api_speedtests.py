import csv
from datetime import datetime, timedelta
import os
import asyncio
import argparse
import ipaddress
from typing import Dict, List
import sys
from timeit import default_timer as timer


import meraki.aio

# Either input your API key below, or set an environment variable
# for example, in Terminal on macOS:  export MERAKI_DASHBOARD_API_KEY=66839003d2861bc302b292eb66d3b247709f2d0d
api_key = ""

WAIT = 1


async def processNetworks(aiomeraki: meraki.aio.AsyncDashboardAPI, org):
    try:
        networks = await aiomeraki.organizations.getOrganizationNetworks(org["id"])
        for net in networks:
            print(net["name"])
    except meraki.AsyncAPIError as e:
        print(f"processNetworks: Meraki API error: {e}")
    except Exception as e:
        print(f"processNetworks: error: {e}")
    return


async def processNetworksWithOwnAPI(org):
    try:
        async with meraki.aio.AsyncDashboardAPI(
            api_key=api_key,
            base_url="https://api.meraki.com/api/v1",
            suppress_logging=True,
            maximum_concurrent_requests=200,
            nginx_429_retry_wait_time=WAIT,
            retry_4xx_error_wait_time=WAIT,
        ) as aiomeraki:
            networks = await aiomeraki.organizations.getOrganizationNetworks(org["id"])
            for net in networks:
                print(net["name"])
    except meraki.AsyncAPIError as e:
        print(f"processNetworks: Meraki API error: {e}")
    except Exception as e:
        print(f"processNetworks: error: {e}")
    return


async def api_per_org_max_3():
    async with meraki.aio.AsyncDashboardAPI(
        api_key=api_key,
        base_url="https://api.meraki.com/api/v1",
        suppress_logging=True,
        maximum_concurrent_requests=3,
        nginx_429_retry_wait_time=WAIT,
        retry_4xx_error_wait_time=WAIT,
    ) as aiomeraki:
        # Get list of organizations to which API key has access
        orgs = await aiomeraki.organizations.getOrganizations()
        orgTasks = [processNetworksWithOwnAPI(org) for org in orgs]
        for task in asyncio.as_completed(orgTasks):
            await task


async def api_per_org_max_200():
    async with meraki.aio.AsyncDashboardAPI(
        api_key=api_key,
        base_url="https://api.meraki.com/api/v1",
        suppress_logging=True,
        maximum_concurrent_requests=200,
        nginx_429_retry_wait_time=WAIT,
        retry_4xx_error_wait_time=WAIT,
    ) as aiomeraki:
        # Get list of organizations to which API key has access
        orgs = await aiomeraki.organizations.getOrganizations()
        orgTasks = [processNetworksWithOwnAPI(org) for org in orgs]
        for task in asyncio.as_completed(orgTasks):
            await task


async def max3():
    async with meraki.aio.AsyncDashboardAPI(
        api_key=api_key,
        base_url="https://api.meraki.com/api/v1",
        suppress_logging=True,
        maximum_concurrent_requests=3,
        nginx_429_retry_wait_time=WAIT,
        retry_4xx_error_wait_time=WAIT,
    ) as aiomeraki:
        # Get list of organizations to which API key has access
        orgs = await aiomeraki.organizations.getOrganizations()
        for org in orgs:
            print(org["id"] + " " + org["name"])

        orgTasks = [processNetworks(aiomeraki, org) for org in orgs]
        for task in asyncio.as_completed(orgTasks):
            await task


async def max200():
    async with meraki.aio.AsyncDashboardAPI(
        api_key=api_key,
        base_url="https://api.meraki.com/api/v1",
        suppress_logging=True,
        maximum_concurrent_requests=200,
        nginx_429_retry_wait_time=WAIT,
        retry_4xx_error_wait_time=WAIT,
    ) as aiomeraki:
        # Get list of organizations to which API key has access
        orgs = await aiomeraki.organizations.getOrganizations()
        for org in orgs:
            print(org["id"] + " " + org["name"])

        orgTasks = [processNetworks(aiomeraki, org) for org in orgs]
        for task in asyncio.as_completed(orgTasks):
            await task


async def max200_mp():
    async with meraki.aio.AsyncDashboardAPI(
        api_key=api_key,
        base_url="https://api-mp.meraki.com/api/v1",
        suppress_logging=True,
        maximum_concurrent_requests=200,
        nginx_429_retry_wait_time=WAIT,
        retry_4xx_error_wait_time=WAIT,
    ) as aiomeraki:
        # Get list of organizations to which API key has access
        orgs = await aiomeraki.organizations.getOrganizations()
        for org in orgs:
            print(org["id"] + " " + org["name"])

        orgTasks = [processNetworks(aiomeraki, org) for org in orgs]
        for task in asyncio.as_completed(orgTasks):
            await task


async def main():
    methods = [max3, max200, max200_mp, api_per_org_max_200, api_per_org_max_3]
    times = {}
    for m in methods:
        print(f"testing {m.__name__}")
        start = timer()
        await m()
        end = timer()
        print(f"elapsed {end-start} seconds")
        times[m.__name__] = end - start
        await asyncio.sleep(5)

    for x, y in times.items():
        print(f"{x} took {y} seconds")

    print("Script complete!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
