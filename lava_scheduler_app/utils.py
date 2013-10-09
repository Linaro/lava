# Copyright (C) 2013 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Senthil Kumaran <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Scheduler.
#
# LAVA Scheduler is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3 as
# published by the Free Software Foundation
#
# LAVA Scheduler is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Scheduler.  If not, see <http://www.gnu.org/licenses/>.

import re
import copy
import socket
import urlparse
import simplejson
import models


def rewrite_hostname(result_url):
    """If URL has hostname value as localhost/127.0.0.*, change it to the
    actual server FQDN.

    Returns the RESULT_URL (string) re-written with hostname.

    See https://cards.linaro.org/browse/LAVA-611
    """
    host = urlparse.urlparse(result_url).netloc
    if host == "localhost":
        result_url = result_url.replace("localhost", socket.getfqdn())
    elif host.startswith("127.0.0"):
        ip_pat = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        result_url = re.sub(ip_pat, socket.getfqdn(), result_url)
    return result_url


def split_multi_job(json_jobdata, target_group):
    node_json = {}
    all_nodes = {}
    node_actions = {}
    node_lmp = {}

    # Check if we are operating on multinode job data. Else return the job
    # data as it is.
    if "device_group" in json_jobdata and target_group:
        pass
    else:
        return json_jobdata

    # get all the roles and create node action list for each role.
    for group in json_jobdata["device_group"]:
        node_actions[group["role"]] = []
        node_lmp[group["role"]] = []

    # Take each action and assign it to proper roles. If roles are not
    # specified for a specific action, then assign it to all the roles.
    all_actions = json_jobdata["actions"]
    for role in node_actions.keys():
        for action in all_actions:
            new_action = copy.deepcopy(action)
            if 'parameters' in new_action \
                    and 'role' in new_action["parameters"]:
                if new_action["parameters"]["role"] == role:
                    new_action["parameters"].pop('role', None)
                    node_actions[role].append(new_action)
            else:
                node_actions[role].append(new_action)

    if "lmp_module" in json_jobdata:
        # For LMP init in multinode case
        all_lmp_modules = json_jobdata["lmp_module"]
        for role in node_lmp.keys():
            for lmp in all_lmp_modules:
                new_lmp = copy.deepcopy(lmp)
                if 'parameters' in new_lmp \
                        and 'role' in new_lmp["parameters"]:
                    if new_lmp["parameters"]["role"] == role:
                        new_lmp["parameters"].pop('role', None)
                        node_lmp[role].append(new_lmp)
                else:
                    node_lmp[role].append(new_lmp)

    group_count = 0
    for clients in json_jobdata["device_group"]:
        group_count += int(clients["count"])
    if group_count <= 1:
        raise models.JSONDataError("Only one device requested in a MultiNode job submission.")
    for clients in json_jobdata["device_group"]:
        role = str(clients["role"])
        count = int(clients["count"])
        node_json[role] = []
        for c in range(0, count):
            node_json[role].append({})
            node_json[role][c]["timeout"] = json_jobdata["timeout"]
            if json_jobdata.get("job_name", False):
                node_json[role][c]["job_name"] = json_jobdata["job_name"]
            if clients.get("tags", False):
                node_json[role][c]["tags"] = clients["tags"]
            node_json[role][c]["group_size"] = group_count
            node_json[role][c]["target_group"] = target_group
            node_json[role][c]["actions"] = node_actions[role]
            if "lmp_module" in json_jobdata:
                node_json[role][c]["lmp_module"] = node_lmp[role]

            node_json[role][c]["role"] = role
            # multinode node stage 2
            if json_jobdata.get("logging_level", False):
                node_json[role][c]["logging_level"] = \
                    json_jobdata["logging_level"]
            if json_jobdata.get("priority", False):
                node_json[role][c]["priority"] = json_jobdata["priority"]
            node_json[role][c]["device_type"] = clients["device_type"]

    return node_json


def requested_device_count(json_data):
    """Utility function check the requested number of devices for each
    device_type in a multinode job.

    JSON_DATA is the job definition string.

    Returns requested_device which is a dictionary of the following format:

    {'kvm': 1, 'qemu': 3, 'panda': 1}

    If the job is not a multinode job, then return an empty dictionary.
    """
    job_data = simplejson.loads(json_data)
    requested_devices = {}
    if 'device_group' in job_data:
        for device_group in job_data['device_group']:
            device_type = device_group['device_type']
            count = device_group['count']
            if device_type in requested_devices:
                requested_devices[device_type] += count
            else:
                requested_devices[device_type] = count
    return requested_devices
