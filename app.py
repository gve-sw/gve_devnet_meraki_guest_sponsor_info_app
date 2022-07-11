# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (c) 2022 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

__author__ = "Simon Fang <sifang@cisco.com>"
__copyright__ = "Copyright (c) 2022 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"

from flask import Flask, render_template, request, make_response
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd

# Global variables
app = Flask(__name__)

BASE_URL = "https://account.meraki.com"
MERAKI_API_URL = "https://dashboard.meraki.com/api"


# Establish a session
session = requests.Session()

# Helper Functions
def post_login_credentials(username, password):
    global ORG_URLS
    print("*** Posting the login credentials to the dashboard ***")
    url = f'{BASE_URL}/login/login'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    body = {
        'email': username,
        'password': password
    }
    response = session.post(url, data=body, headers=headers)

    if "Please contact your network administrator for assistance" in response.text:
        print("*** An error has occurred and posting login credentials was not successful ***")
        return 0

    print("*** Getting the org url from the org list ***")
    url = f'{BASE_URL}/login/org_list'
    response = session.get(url)

    if response.ok:
        soup = BeautifulSoup(response.content, 'html.parser')
        ORG_URLS = soup.find_all('a')
        print("*** The login credentials were successfully posted ***")
        print("*** The org list was successfully obtained ***")
        return 1
    else:
        print("*** Posting login credentials was not successful")
        print(response.text)
        return 0

def get_organizations():
    url = f"{MERAKI_API_URL}/v1/organizations"
    headers = {
        'X-Cisco-Meraki-API-Key': API_KEY
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    organizations = response.json()
    return organizations

def get_org_url_from_org_list(organization):
    for tag in ORG_URLS:
        if organization in tag:
            org_url = tag.get('href')
            return org_url
    # Could not find org url
    print(f"Org_url could not be obtained for {organization}")
    return None

def get_dashboard_base_url(org_url):
    print("*** Getting the dashboard base url ***")
    # Choose org
    url = f'{BASE_URL}{org_url}'
    response = session.get(url)
    if response.history:
        print("The request was redirected to the following dashboard url:")
        # Obtain last redirect url
        dashboard_url = response.history[-1].url
        # Remove dashboard from dashboard url
        DASHBOARD_BASE_URL = dashboard_url[:-10]
        print(DASHBOARD_BASE_URL)
        return DASHBOARD_BASE_URL
    else:
        print("Request was not redirected")
        return 

def get_organization_id(organization_name):
    
    for org in ORGANIZATIONS:
        if org['name'] == organization_name:
            return org['id']
    return None


def get_networks(organization_id):
    url = f"{MERAKI_API_URL}/v1/organizations/{organization_id}/networks"
    headers = {
        'X-Cisco-Meraki-API-Key': API_KEY
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    networks = response.json()
    return networks

def get_ssids(network_id):
    url = f"{MERAKI_API_URL}/v1/networks/{network_id}/wireless/ssids"
    headers = {
        'X-Cisco-Meraki-API-Key': API_KEY
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    SSIDs = response.json()
    return SSIDs

def get_clients_connected_to_guest_SSID(SSID):
    print("Let's obtain the clients connected to the guest SSID")
    url = f'{MERAKI_API_URL}/v0/networks/{NETWORK_ID}/clients'
    headers = {
        'X-Cisco-Meraki-API-Key': API_KEY
    }
    response = requests.get(url, headers=headers)
    if response.ok:
        print("*** The list of clients connected to the guest SSID was successfully obtained ***")
    response.raise_for_status()
    guest_clients = []
    for client in response.json():
        if client['ssid'] == SSID:
            guest_clients.append(client['id'])

    return guest_clients

def get_AP_from_clients_endpoint(DASHBOARD_BASE_URL, client_id):
    url = f"{MERAKI_API_URL}/v1/networks/{NETWORK_ID}/clients?perPage=1000" #adapt code if there are more than 1000 clients
    headers = {
        'X-Cisco-Meraki-API-Key': API_KEY
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    clients = response.json()
    for client in clients:
        if client["id"] == client_id:
            ap = client["recentDeviceName"]
            return ap
    return None

def get_date_time_from_last_seen(epoch_time):
    date_time = datetime.fromtimestamp(int(epoch_time))
    date_time_string_format = date_time.strftime('%Y/%m/%d %H:%M')
    return date_time_string_format

def get_splash_info_per_client_id(DASHBOARD_BASE_URL, client_id):
    url = f"{DASHBOARD_BASE_URL}/usage/client_show/{client_id}?t0=&t1=&timespan=86400&filter="
    headers = {
        'X-Requested-With': 'XMLHttpRequest'
    }

    response = session.get(url=url, headers=headers)
    if response.ok:
        print("*** The splash infos per client ID was successfully obtained ***")

    splash_info = {}
    client_info = response.json()

    splash_info['description'] = client_info['description']
    splash_info['last_seen'] = get_date_time_from_last_seen(client_info['last_seen'])
    splash_info['os'] = client_info['os']
    splash_info['ip'] = client_info['ip']
    splash_info['mac'] = client_info["mac"]
    splash_info['sponsor_email'] = client_info['wireless_bigacl'][0]['sponsor_email']
    splash_info['authorized'] = client_info['wireless_bigacl'][0]['authorized']
    splash_info['expires'] = client_info['wireless_bigacl'][0]['expires']
    splash_info['AP'] = get_AP_from_clients_endpoint(DASHBOARD_BASE_URL, client_id)
    splash_info['ssid'] = client_info["ssid_name"]
    return splash_info

def get_csv_from_splash_infos(splash_infos):
    try:
        print("*** Writing to csv ***")
        df = pd. DataFrame(splash_infos)
        # file_path = f"csv_reports/{datetime.now().strftime('%Y%m%d_%H%M')}_splash_infos_{SSID.replace(' ', '_')}.csv"
        csv = df.to_csv(index=False)
        print("*** Writing to csv was successful***")
        return csv
        
    except Exception as e:
        print(e)

# Routes
## Main page
@app.route('/')
def main():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        form_data = request.form
        print(form_data)

        username = form_data['username']
        password = form_data['password']

        if post_login_credentials(username, password):
            return render_template('api_key.html')

    return render_template('login.html')

@app.route('/submit_api_key', methods=['POST'])
def submit_api_key():
    global API_KEY
    global ORGANIZATIONS
    if request.method == 'POST':
        form_data = request.form
        print(form_data)

        API_KEY = form_data['api_key']

        ORGANIZATIONS = get_organizations()
        return render_template('organizations.html', organizations=ORGANIZATIONS)
    return render_template('login.html')

@app.route('/select_organization', methods=['POST'])
def select_organization():
    global DASHBOARD_BASE_URL
    if request.method == 'POST':
        form_data = request.form
        print(form_data)

        organization = form_data['organization']
        
        org_url = get_org_url_from_org_list(organization)

        if not org_url:
            return render_template('login.html')

        DASHBOARD_BASE_URL = get_dashboard_base_url(org_url)
        
        organization_id = get_organization_id(organization)
        if not organization_id:
            print("Error: no organization id")
        networks = get_networks(organization_id)

        return render_template('networks.html', networks=networks)
    return render_template('login.html')


@app.route('/select_ssid', methods=['POST'])
def select_ssid():
    global SSIDs
    global NETWORK_ID
    if request.method == 'POST':
        form_data = request.form
        print(form_data)

        NETWORK_ID = form_data['network']

        SSIDs = get_ssids(NETWORK_ID)
        return render_template('ssid.html', SSIDs=SSIDs, selected_ssid=None, splash_infos=[])


@app.route('/submit_ssid', methods=['POST'])
def submit_ssid():
    global SPLASH_INFOS
    global SELECTED_SSID
    if request.method == 'POST':
        form_data = request.form
        print(form_data)

        SELECTED_SSID = form_data['ssid']

        guest_clients = get_clients_connected_to_guest_SSID(SELECTED_SSID)

        # get splash infos for selected ssid
        SPLASH_INFOS = []
        # Get splash info per client id
        for client_id in guest_clients:
            splash_info = get_splash_info_per_client_id(DASHBOARD_BASE_URL, client_id)
            SPLASH_INFOS.append(splash_info)

        # # In case there is no data available from the Meraki Dashboard, use dummy data
        # splash_info = {}

        # splash_info['description'] = 'test'
        # splash_info['last_seen'] = '1234'
        # splash_info['os'] = 'os'
        # splash_info['ip'] = '10.10.10.10'
        # splash_info['mac'] = 'aa:bb:cc:11:22:33'
        # splash_info['sponsor_email'] = 'example@mail.com'
        # splash_info['authorized'] = '3 days'
        # splash_info['expires'] = '5 days'
        # splash_info['AP'] = 'example_ap'
        # splash_info['ssid'] = 'Sponsored Guest Two'

        # SPLASH_INFOS = [splash_info]
        
        return render_template('ssid.html', SSIDs=SSIDs, selected_ssid=SELECTED_SSID, splash_infos=SPLASH_INFOS)
    return render_template('login.html')

@app.route("/download_csv", methods=['POST'])
def download_csv():
    if request.method == 'POST':
        form_data = request.form
        print(form_data)

        try:
            # User clicked button to download csv
            form_data['download_button']

            csv = get_csv_from_splash_infos(SPLASH_INFOS)

            response = make_response(csv)

            filename = f"{datetime.now().strftime('%Y%m%d_%H%M')}_splash_infos_{SELECTED_SSID.replace(' ', '_')}.csv"

            response.headers.set("Content-Disposition", "attachment", filename=filename)

            return response
        except Exception as e:
            print("An error has occurred:")
            print(e)
    return render_template('login.html')


# Run app
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5001, debug=True) #https://127.0.0.1:5001
