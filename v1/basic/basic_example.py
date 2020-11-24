import argparse
import asyncio
import json
import os
import sys

import meraki.aio


async def main():

    parser = argparse.ArgumentParser(description="Example Script with basic arguments")
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
        help="the name/id of the networks.",
    )

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
        networks = []
        if args.organization:
            organizations = await aiomeraki.organizations.getOrganizations()
            for o in organizations:
                if o["id"] == args.organization or o["name"] == args.organization:
                    o_networks = await aiomeraki.organizations.getOrganizationNetworks(
                        o["id"]
                    )
                    print(o_networks)
        print("Script complete!")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
