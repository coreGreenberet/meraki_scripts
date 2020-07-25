Overview
========
This script will analyze and print the usage of subnetPools inside an organization.


Requirements
============

-  Please make sure, that you have the latest meraki api installed (>= 0.100.1) (released on 02.April.2020).

  ```pip3 install meraki -U```

-  Currently there is no API available to read the template configuration. 
  To get the needed information this script will download the configuration changelog from the dashboard 
  and extract the information from there. This also means, that only template changes which were done in the last [14 months to two years](https://documentation.meraki.com/zGeneral_Administration/Organizations_and_Networks/Organization_Menu/Organization_Change_Log#Overview) will be listed here.

Usage
=====

```
usage: aio_list_used_template_ranges.py [-h] -o ORGANIZATIONS
                                        [ORGANIZATIONS ...]

Analyze the usage of subnetPool templates

optional arguments:
  -h, --help            show this help message and exit
  -o ORGANIZATIONS [ORGANIZATIONS ...], --organization ORGANIZATIONS [ORGANIZATIONS ...]
                        the name/id of the organization(s) you want to analyze

```


Example Output
==============

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


How it works
============

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
