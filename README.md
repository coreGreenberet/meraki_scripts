# meraki_scripts
Just a collection of helpful meraki scripts.
All scripts are using the asyncio version of the meraki library

# Table of Contents
1. [API Version V0](#v0)
    1. [aio_create_dummy_orgs.py](#aio_create_dummy_orgs.py)
    2. [aio_list_used_template_ranges.py](#aio_list_used_template_ranges.py)
2. [API Version V1](#v1)
    1. [org2orgVPN ](#org2orgVPN)
    1. [wifi-qrcode ](#wifi-qrcode)

# API Version V0 <a name="v0"></a>

## aio_create_dummy_orgs.py <a name="aio_create_dummy_orgs.py"></a>
This script will generate 200 organizations with 10 networks each. This is helpfull, if you want to test something over more networks.

## aio_list_used_template_ranges.py <a name="aio_list_used_template_ranges.py"></a>

This script will analyze and print the usage of subnetPools inside an organization.


### Requirements

-  Please make sure, that you have the latest meraki api installed (>= 0.100.1) (released on 02.April.2020).

  ```pip3 install meraki -U```

-  Currently there is no API available to read the template configuration. 
  To get the needed information this script will download the configuration changelog from the dashboard 
  and extract the information from there. This also means, that only template changes which were done in the last [14 months to two years](https://documentation.meraki.com/zGeneral_Administration/Organizations_and_Networks/Organization_Menu/Organization_Change_Log#Overview) will be listed here.

### Usage

```
usage: aio_list_used_template_ranges.py [-h] -o ORGANIZATIONS
                                        [ORGANIZATIONS ...]

Analyze the usage of subnetPool templates

optional arguments:
  -h, --help            show this help message and exit
  -o ORGANIZATIONS [ORGANIZATIONS ...], --organization ORGANIZATIONS [ORGANIZATIONS ...]
                        the name/id of the organization(s) you want to analyze

```


### Example Output

```
Analyzing organization Template_Demo
Downloading Changelog
Downloading templates
Analyzing template Template_One
Analyzing template Template_Two
Analyzing template Template_Three
Analyzing template Template_Four
Analyzing template Template_Five
Getting largest supernetworks:
172.16.0.0/21 mask 28
172.16.8.0/21 mask 29
172.16.16.0/21 mask 28
Downloading VLAN information
172.16.0.0/21 mask 28 subnetworks: total=128 used=34 free=94 -> usage 26.5625%
172.16.8.0/21 mask 29 subnetworks: total=256 used=20 free=236 -> usage 7.8125%
172.16.16.0/21 mask 28 subnetworks: total=128 used=32 free=96 -> usage 25.0%
```


### How it works

**Step 1:**

Since we don't have access yet to the address settings in the network template, this script will download the changelog


**Step 2:**

It will download all templates and map all network configuration changes to the templates.
Which also means, that it can only detect networks of a template which got changed in the last 14 months or 2 years. see Meraki Documentation for details 


**Step 3:**

It will search for the biggest standalone supernetworks and map the smallest possible mask.


**Step 4:**

It will download the vlan information of all networks and calculate their usage on their respective supernetwork.


**Step 5:**

Print results

# API Version V1 <a name="v1"></a>

## org2orgVPN <a name="org2orgVPN"></a>
This script will create/update the VPN connection between two meraki
organizations.

```
usage: org2orgVPN.py [-h] -o1 ORGANIZATION1 -o2 ORGANIZATION2
                     [-t1 TAGS1 [TAGS1 ...]] [-t2 TAGS2 [TAGS2 ...]] [-p PSK]
                     [--ike-version IKE_VERSION]

This script will create/update the VPN connection between two meraki
organizations

optional arguments:
  -h, --help            show this help message and exit
  -o1 ORGANIZATION1, --organization1 ORGANIZATION1
                        the name/id of the first organization
  -o2 ORGANIZATION2, --organization2 ORGANIZATION2
                        the name/id of the second organization
  -t1 TAGS1 [TAGS1 ...], --tags1 TAGS1 [TAGS1 ...]
                        the tags from the first organization to grab the vpn
                        networks and remote IPs. Leave Empty for all
  -t2 TAGS2 [TAGS2 ...], --tags2 TAGS2 [TAGS2 ...]
                        the tags from the second organization to grab the vpn
                        networks and remote IPs. Leave Empty for all
  -p PSK, --psk PSK     the psk for the vpn connection. Use "random" to
                        generate a random key
  --ike-version IKE_VERSION
                        the IKE version. Must be 1 or 2
```


## wifi-qrcode <a name="wifi-qrcode"></a>
This script will generate QRCodes for configured SSIDs. 
You have to provide at least the organization or network parameter. 

the QRCodes will be places in a subdirectory "img". The Filename is {NetworkName}_{SSID}.png.

```
usage: generate_qrcodes.py [-h] [-o ORGANIZATION] [-n NETWORKS [NETWORKS ...]]
                           [-s SSIDS [SSIDS ...]]

Generates QRCodes from Meraki wireless networks

optional arguments:
  -h, --help            show this help message and exit
  -o ORGANIZATION, --organization ORGANIZATION
                        the name/id of the organization
  -n NETWORKS [NETWORKS ...], --network NETWORKS [NETWORKS ...]
                        the name/id of the networks to generate the qr codes
                        from.  If you are providing this parameter, then you must 
                        provide the organization.
  -s SSIDS [SSIDS ...], --ssid SSIDS [SSIDS ...]
                        the name of the ssids to generate the qr codes```
