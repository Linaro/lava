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

import json
import copy
from socket import gethostname


def split_multi_job(multi_job_data, target_group):
    group_json = {}
    node_json = {}
    all_nodes = {}
    node_actions = {}
    hostname = gethostname()
    port = 3079
    json_jobdata = multi_job_data
    if "device_group" in json_jobdata:
        # multinode start, group stage 1
        group_json["timeout"] = json_jobdata["timeout"]
        group_json["group_dispatcher"] = True
        # group stage 2 - configurable values
        # all the groupd_dispatcher really needs is the port number to use
        group_json["logging_level"] = "DEBUG"
        group_json["port"] = port
        group_json["hostname"] = hostname
        # multinode node stage 1
        for actions in json_jobdata["actions"]:
            if "parameters" not in actions \
                    or 'role' not in actions["parameters"]:
                continue
            role = str(actions["parameters"]["role"])
            node_actions[role] = []
        for actions in json_jobdata["actions"]:
            if "parameters" not in actions \
                    or 'role' not in actions["parameters"]:
                # add to each node, e.g. submit_results
                all_nodes[actions["command"]] = actions
                continue
            role = str(actions["parameters"]["role"])
            actions["parameters"].pop('role', None)
            node_actions[role].append({"command": actions["command"],
                                       "parameters": actions["parameters"]})
        group_count = 0
        for clients in json_jobdata["device_group"]:
            group_count += int(clients["count"])
        for clients in json_jobdata["device_group"]:
            role = str(clients["role"])
            count = int(clients["count"])
            node_json[role] = []
            for c in range(0, count):
                node_json[role].append({})
                node_json[role][c]["timeout"] = json_jobdata["timeout"]
                node_json[role][c]["job_name"] = json_jobdata["job_name"]
                node_json[role][c]["tags"] = clients["tags"]
                node_json[role][c]["group_size"] = group_count
                node_json[role][c]["target_group"] = target_group
                node_json[role][c]["actions"] = copy.deepcopy(
                    node_actions[role])
                for key in all_nodes:
                    node_json[role][c]["actions"].append(all_nodes[key])
                node_json[role][c]["role"] = role
                # multinode node stage 2
                node_json[role][c]["logging_level"] = "DEBUG"
                node_json[role][c]["port"] = port
                node_json[role][c]["hostname"] = hostname
                node_json[role][c]["device_type"] = clients["device_type"]

        return (node_json, group_json)

    return 0
