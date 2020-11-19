# Copyright (C) 2019 Linaro Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import glob
import logging
import logging.handlers
import os
import subprocess
import pyudev

from lava_common.compat import yaml_dump, yaml_load
from lava_common.constants import DISPATCHER_DOWNLOAD_DIR as JOBS_DIR
from lava_common.exceptions import InfrastructureError

context = pyudev.Context()

logger = logging.getLogger("lava-dispatcher-host")
logger.addHandler(logging.handlers.SysLogHandler(address="/dev/log"))
logger.setLevel(logging.INFO)


def get_mapping_path(job_id):
    return os.path.join(JOBS_DIR, job_id, "usbmap.yaml")


def add_device_container_mapping(job_id, device_info, container, container_type="lxc"):
    validate_device_info(device_info)
    item = {
        "device_info": device_info,
        "container": container,
        "container_type": container_type,
        "job_id": job_id,
    }
    mapping_path = get_mapping_path(job_id)
    data = load_mapping_data(mapping_path)

    # remove old mappings for the same device_info
    newdata = [old for old in data if old["device_info"] != item["device_info"]]
    newdata.append(item)

    os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
    with open(mapping_path, "w") as f:
        f.write(yaml_dump(newdata))


def remove_device_container_mappings(job_id):
    os.unlink(get_mapping_path(job_id))


def validate_device_info(device_info):
    if not device_info:
        raise ValueError("Addind mapping for empty device info: %r" % device_info)
    if not any(device_info.values()):
        raise ValueError(
            "Addind mapping for device info with empty keys: %r" % device_info
        )


def share_device_with_container(options):
    data = find_mapping(options)
    if not data:
        return
    container = data["container"]
    device = options.device
    if not device.startswith("/dev/"):
        device = "/dev/" + device
    if not os.path.exists(device):
        logger.warning("Can't share {device}: file not found".format(device=device))
        return

    container_type = data["container_type"]
    if container_type == "lxc":
        share_device_with_container_lxc(container, device)
    elif container_type == "docker":
        share_device_with_container_docker(container, device)
    else:
        raise InfrastructureError('Unsupported container type: "%s"' % container_type)


def find_mapping(options):
    for mapping in glob.glob(get_mapping_path("*")):
        data = load_mapping_data(mapping)
        for item in data:
            if match_mapping(item["device_info"], options):
                return item
    return None


def load_mapping_data(filename):
    try:
        with open(filename) as f:
            data = yaml_load(f)
        if isinstance(data, dict):
            data = [data]
        return data
    except FileNotFoundError:
        return []


def match_mapping(device_info, options):
    matched = False
    for k, v in device_info.items():
        if v:
            if k in options and getattr(options, k) == v:
                matched = True
            else:
                return False
        else:
            matched = True
    return matched


def log_sharing_device(device, container_type, container):
    logger.info(f"Sharing {device} with {container_type} container {container}")


def share_device_with_container_lxc(container, node):
    log_sharing_device(node, "lxc", container)
    subprocess.check_call(["lxc-device", "-n", container, "add", node])

    device = pyudev.Devices.from_device_file(context, node)
    for child in device.children:
        if child.device_node:
            subprocess.check_call(
                ["lxc-device", "-n", container, "add", child.device_node]
            )


def pass_device_into_container_docker(container, container_id, node, links=[]):
    try:
        nodeinfo = os.stat(node)
        major = os.major(nodeinfo.st_rdev)
        minor = os.minor(nodeinfo.st_rdev)
        with open(
            "/sys/fs/cgroup/devices/docker/%s/devices.allow" % container_id, "w"
        ) as allow:
            allow.write("a %d:%d rwm\n" % (major, minor))
    except FileNotFoundError as exc:
        logger.warning(
            "Cannot share {node} with docker container {container}: {exc.filename} not found"
        )
        return

    # it's ok to fail; container might have already exited at this point.
    subprocess.call(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-c",
            "mkdir -p %s && mknod %s c %d %d"
            % (os.path.dirname(node), node, major, minor),
        ]
    )

    for link in links:
        subprocess.call(
            [
                "docker",
                "exec",
                container,
                "sh",
                "-c",
                f"mkdir -p {os.path.dirname(link)} && ln -f -s {node} {link}",
            ]
        )


def share_device_with_container_docker(container, node):
    log_sharing_device(node, "docker", container)
    try:
        container_id = subprocess.check_output(
            ["docker", "inspect", "--format={{.ID}}", container], text=True
        ).strip()
    except subprocess.CalledProcessError:
        logger.warning(
            f"Cannot share {node} with docker container {container}: container not found"
        )
        return

    device = pyudev.Devices.from_device_file(context, node)
    pass_device_into_container_docker(
        container, container_id, node, device.device_links
    )

    for child in device.children:
        if child.device_node:
            pass_device_into_container_docker(
                container, container_id, child.device_node, child.device_links
            )
