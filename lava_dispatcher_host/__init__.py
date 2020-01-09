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
import os
import subprocess

from lava_common.compat import yaml_dump, yaml_load
from lava_common.constants import DISPATCHER_DOWNLOAD_DIR as JOBS_DIR
from lava_common.exceptions import InfrastructureError


def get_mapping_path(job_id):
    return os.path.join(JOBS_DIR, job_id, "usbmap.yaml")


def add_device_container_mapping(
    job_id, device_info, container, container_type="lxc", logging_info={}
):
    data = {
        "device_info": device_info,
        "container": container,
        "container_type": container_type,
        "logging_info": logging_info,
    }
    logger = logging.getLogger("dispatcher")
    mapping_path = get_mapping_path(job_id)
    os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
    with open(mapping_path, "w") as f:
        f.write(yaml_dump(data))
        logger.info(
            "Added mapping for {device_info} to {container_type} container {container}".format(
                **data
            )
        )


def share_device_with_container(options, setup_logger=None):
    data = find_mapping(options)
    if not data:
        return
    if setup_logger:
        setup_logger(data["logging_info"])
    logger = logging.getLogger("dispatcher")
    container = data["container"]
    device = "/dev/" + options.device
    if not os.path.exists(device):
        logger.warning("Can't share {device}: file not found".format(device=device))
        return

    container_type = data["container_type"]
    if container_type == "lxc":
        share_device_with_container_lxc(container, device)
    else:
        raise InfrastructureError('Unsupported container type: "%s"' % container_type)

    logger.info(
        "Sharing {device} with {container_type} container {container}".format(
            device=device,
            container_type=data["container_type"],
            container=data["container"],
        )
    )


def find_mapping(options):
    for mapping in glob.glob(get_mapping_path("*")):
        data = yaml_load(open(mapping))
        if match_mapping(data["device_info"], options):
            return data
    return None


def match_mapping(device_info, options):
    for k, v in device_info.items():
        if k in options and v and getattr(options, k) != v:
            return False
    return True


def share_device_with_container_lxc(container, node):
    subprocess.check_call(["lxc-device", "-n", container, "add", node])
