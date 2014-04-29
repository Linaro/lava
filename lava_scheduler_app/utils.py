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

import os
import re
import copy
import uuid
import socket
import urlparse
import simplejson
import models
import subprocess
import datetime

from collections import OrderedDict

from django.contrib.sites.models import Site

from lava_server.settings.getsettings import Settings
from lava_server.settings.config_file import ConfigFile


def rewrite_hostname(result_url):
    """If URL has hostname value as localhost/127.0.0.*, change it to the
    actual server FQDN.

    Returns the RESULT_URL (string) re-written with hostname.

    See https://cards.linaro.org/browse/LAVA-611
    """
    domain = socket.getfqdn()
    try:
        site = Site.objects.get_current()
    except (Site.DoesNotExist, ImproperlyConfigured):
        pass
    else:
        domain = site.domain

    if domain == 'example.com' or domain == 'www.example.com':
        domain = get_ip_address()

    host = urlparse.urlparse(result_url).netloc
    if host == "localhost":
        result_url = result_url.replace("localhost", domain)
    elif host.startswith("127.0.0"):
        ip_pat = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        result_url = re.sub(ip_pat, domain, result_url)
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


def split_vm_job(json_jobdata, vm_group):
    node_json = {}
    all_nodes = {}
    node_actions = {}
    vms_list = []

    # Check if we are operating on vm_group job data. Else return the job
    # data as it is.
    if "vm_group" in json_jobdata and vm_group:
        pass
    else:
        raise Exception('Invalid vm_group data')

    # Get the VM host details.
    device_type = json_jobdata['vm_group']['host']['device_type']
    role = json_jobdata['vm_group']['host']['role']
    is_vmhost = True
    vms_list.append((device_type, role, 1, is_vmhost))  # where 1 is the count

    # Get all other constituting VMs.
    for vm in json_jobdata['vm_group']['vms']:
        device_type = vm['device_type']
        count = int(vm.get('count', 1))
        role = vm.get('role', None)
        is_vmhost = False
        vms_list.append((device_type, role, count, is_vmhost))

    # get all the roles and create node action list for each role.
    for vm in vms_list:
        node_actions[vm[1]] = []

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

    group_count = 0
    for vm in vms_list:
        group_count += int(vm[2])

    group_counter = group_count
    for vm in vms_list:
        role = vm[1]
        count = int(vm[2])
        node_json[role] = []
        is_vmhost = vm[3]
        for c in range(0, count):
            node_json[role].append({})
            node_json[role][c]["timeout"] = json_jobdata["timeout"]
            node_json[role][c]["is_vmhost"] = is_vmhost
            if json_jobdata.get("job_name", False):
                node_json[role][c]["job_name"] = json_jobdata["job_name"]
            node_json[role][c]["group_size"] = group_count
            node_json[role][c]["target_group"] = vm_group
            node_json[role][c]["actions"] = node_actions[role]
            node_json[role][c]["role"] = role
            # vm_group node stage 2
            if json_jobdata.get("logging_level", False):
                node_json[role][c]["logging_level"] = \
                    json_jobdata["logging_level"]
            if json_jobdata.get("priority", False):
                node_json[role][c]["priority"] = json_jobdata["priority"]
            if is_vmhost:
                node_json[role][c]["device_type"] = vm[0]
            else:
                node_json[role][c]["device_type"] = "dynamic-vm"
                node_json[role][c]["config"] = {
                    "device_type": "dynamic-vm",
                    "dynamic_vm_backend_device_type": vm[0],
                }
                node_json[role][c]["target"] = 'vm%d' % group_counter
        group_counter -= 1

    return node_json


def is_master():
    """Checks if the current machine is the master.
    """
    worker_config_path = '/etc/lava-server/worker.conf'
    if "VIRTUAL_ENV" in os.environ:
        worker_config_path = os.path.join(os.environ["VIRTUAL_ENV"],
                                          worker_config_path[1:])

    return not os.path.exists(worker_config_path)


def get_uptime():
    """Return the system uptime string.
    """
    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        uptime = str(datetime.timedelta(seconds=uptime_seconds))
        return uptime


def get_lshw_out():
    """Return the output of lshw command in html format.
    """
    lshw_cmd = "lshw -html"
    proc = subprocess.Popen(lshw_cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    lshw_out, lshw_err = proc.communicate()
    return simplejson.dumps(lshw_out)


def get_fqdn():
    """Returns the fully qualified domain name.
    """
    return socket.getfqdn()


def get_ip_address():
    """Returns the IP address.
    """
    return socket.gethostbyname_ex(socket.getfqdn())[2][0]


def format_sw_info_to_html(data_dict):
    """Formats the given software info DATA_DICT to viewable html.
    """
    ordered_data_dict = OrderedDict(sorted(data_dict.items()))
    html_content = '<table>\n'
    html_content += '<tr>\n<th>Software</th>\n<th>Information</th>\n</tr>\n'
    for k, v in ordered_data_dict.iteritems():
        html_content += '<tr>\n<td>%s</td>\n<td>%s</td>\n</tr>\n' % (k, v)

    return html_content


def installed_packages(prefix=None, package_name=None):
    """Queries dpkg and filters packages that are related to PACKAGE_NAME.

    PREFIX is the installation prefix for the given instance ie.,
    '/srv/lava/instances/<instance_name>/' which is used for finding out the
    installed package via the python environment.

    Returns a dictionary of packages where the key is the package and the value
    is the package version.
    """
    packages = {}
    if package_name:
        package_cmd = "dpkg -l | grep %s" % package_name
        proc = subprocess.Popen(package_cmd, shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        package_out, package_err = proc.communicate()
        pack_re = re.compile("ii\s+(?P<package>\S+)\s+(?P<version>\S+)\s+.*",
                             re.MULTILINE)
        for package in pack_re.findall(package_out):
            packages[package[0]] = package[1]

    # Find packages via the python environment for this instance.
    if prefix:
        python_path = os.path.join(prefix, 'bin/python')
        cmd = "grep exports %s" % python_path
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate()

        # The output of the command looks like the following, which is a
        # string, we process this string to populate the package dictionary.
        #
        # '/srv/lava/.cache/git-cache/exports/lava-android-test/2013.12',
        # '/srv/lava/.cache/git-cache/exports/linaro-dashboard-bundle/2013.12',
        if out:
            out = out.replace("'", '')
            for path in out.split(','):
                path = path.strip()
                if path:
                    path = path.replace("'", '')
                    key = os.path.basename(os.path.dirname(path))
                    value = os.path.basename(path)
                    packages[key] = value

    return packages


def local_diffstat(prefix):
    """If there are local build outs available. Get the diffstat of the same.
    PREFIX is the directory to search for local build outs.

    Returns a dictionary of diffstat where the key is the package and the value
    is the diffstat output.
    """
    diffstat = {}

    local_buildout_path = os.path.join(prefix, 'code/current/local')
    for d in os.listdir(local_buildout_path):
        diffstat_cmd = "cd %s; git diff | diffstat;" % \
            os.path.join(local_buildout_path, d)
        proc = subprocess.Popen(diffstat_cmd, shell=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        diffstat_out, diffstat_err = proc.communicate()
        if diffstat_out:
            diffstat_out = '<br />'.join(diffstat_out.split('\n'))
            diffstat[d + '-local-buildout'] = diffstat_out
        else:
            diffstat[d + '-local-buildout'] = diffstat_err

    return diffstat


def get_software_info():
    """Returns git status and version information for LAVA related software.
    """
    sw_info = {}

    # Populate the git status of server code from exports directory.
    settings = Settings("lava-server")
    instance_config_path = settings._get_pathname("instance")
    instance_config = ConfigFile.load(instance_config_path)
    prefix = os.path.join(instance_config.LAVA_PREFIX,
                          instance_config.LAVA_INSTANCE)

    # Populate installed packages.
    sw_info.update(installed_packages(package_name='lava'))
    sw_info.update(installed_packages(package_name='linaro'))
    sw_info.update(installed_packages(prefix=prefix))

    # Summary of local build outs, if any.
    if instance_config.LAVA_DEV_MODE == 'yes':
        sw_info.update(local_diffstat(prefix))

    return simplejson.dumps(format_sw_info_to_html(sw_info))


def get_heartbeat_timeout():
    """Returns the HEARTBEAT_TIMEOUT value specified in worker.conf

    If there is no value found, we return a default timeout value 300.
    """
    settings = Settings("lava-server")
    worker_config_path = settings._get_pathname("worker")
    try:
        worker_config = ConfigFile.load(worker_config_path)
        if worker_config and worker_config.HEARTBEAT_TIMEOUT != '':
            return int(worker_config.HEARTBEAT_TIMEOUT)
        else:
            return 300
    except (IOError, AttributeError):
        return 300


# Private variable to record scheduler tick, which shouldn't be accessed from
# other modules, except via the following APIs.
__last_scheduler_tick = datetime.datetime.utcnow()


def record_scheduler_tick():
    """Records the scheduler tick timestamp in the global variable
    __last_scheduler_tick
    """
    global __last_scheduler_tick
    __last_scheduler_tick = datetime.datetime.utcnow()


def last_scheduler_tick():
    """Returns datetime.dateime object of last scheduler tick timestamp.
    """
    return __last_scheduler_tick
