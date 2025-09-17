#!/usr/bin/python3
#
# Copyright 2025 Arm Ltd
#
# Author: Mark Brown <broonie@kernel.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import asyncio
import os
import sys
from datetime import datetime, timezone

import aioxmlrpc.client
import yaml


def load_labs():
    """load_labs"""
    labs = {}
    lava_cfg = os.path.expanduser("~/.config/lavacli.yaml")

    with open(lava_cfg, "r", encoding="utf-8") as lava_cfg_file:
        lavacfg = yaml.safe_load(lava_cfg_file)
        for lab in lavacfg.keys():
            lab_rpc = lavacfg[lab]["uri"]
            lab_user = lavacfg[lab]["username"]
            lab_token = lavacfg[lab]["token"]

            # The config file stores the /RPC2 but we don't want it later
            lab_url = lab_rpc.removesuffix("/RPC2")

            # ...and we need to sub in the https://
            lab_host = lab_url.removeprefix("https://")
            rpc_url = f"https://{lab_user}:{lab_token}@{lab_host}/RPC2"
            server = aioxmlrpc.client.ServerProxy(rpc_url, allow_none=True)

            labs[lab] = {"server": server, "url": lab_url}

    return labs


async def query_pending(server):
    """pending_jobs_by_device_type"""
    return await server.scheduler.pending_jobs_by_device_type(False)


async def query_device_types(server):
    """device_types.list"""
    return await server.scheduler.device_types.list()


async def query_devices(server):
    """devices.list"""
    return await server.scheduler.devices.list()


# TaskGroup dies on the first exception but we might not have permission
# to view jobs so eat errors here
async def query_job(server, job):
    """show job"""
    try:
        return await server.scheduler.jobs.show(job)
    # pylint: disable-next=W0718
    except Exception as e:
        print("Unable to query", job, e)
        return None


def filter_device_type(lab, device_type, config, pending):
    """should we show this device type in this lab"""
    if device_type["devices"] == 0:
        return True
    type_name = device_type["name"]
    if not type_name in pending:
        return True

    passlist = config.get("passlist")
    if passlist:
        if not lab in passlist:
            return True
        if not type_name in passlist[lab]:
            return True
    return False


# pylint: disable-next=R0913,R0914,R0917
async def check_devices(lab, server, config, device_types, devices, pending):
    """check the devices in one lab"""
    devs = []
    jobs_t = []
    for device_type in device_types:
        if filter_device_type(lab, device_type, config, pending):
            continue

        type_name = device_type["name"]

        # We go type by type to avoid hammering the server too badly
        active = 0
        bad = 0
        jobs_t = []
        async with asyncio.TaskGroup() as tg:
            for d in devices:
                if not d["type"] == type_name:
                    continue
                if d["health"] == "Good":
                    active = active + 1
                if d["health"] == "Unknown":
                    active = active + 1
                if d["health"] == "Bad":
                    bad = bad + 1
                if d["current_job"]:
                    query = tg.create_task(query_job(server, d["current_job"]))
                    jobs_t.append(query)

        jobs = []
        for q in jobs_t:
            if q.result():
                jobs.append(q.result())

        devs.append((lab, type_name, active, bad, pending[type_name], jobs))
    return devs


async def query_lab(lab, server, config):
    """check one lab"""
    # Enumerate the devices, types and active jobs in parallel
    async with asyncio.TaskGroup() as tg:
        pending_t = tg.create_task(query_pending(server))
        device_types_t = tg.create_task(query_device_types(server))
        devices_t = tg.create_task(query_devices(server))

    pending = pending_t.result()
    device_types = device_types_t.result()
    devices = devices_t.result()

    return await check_devices(lab, server, config, device_types, devices, pending)


def read_config():
    """read the config"""
    try:
        config_filename = os.path.expanduser("~/.config/lava-status.yaml")
        with open(config_filename, "r", encoding="utf-8") as config_f:
            return yaml.safe_load(config_f)
    except yaml.YAMLError as e:
        print(f"Failed to parse {config_filename}: {str(e)}")
        sys.exit(1)
    except PermissionError as e:
        print(f"Permission denied opening {config_filename}: {str(e)}")
        sys.exit(1)
    except FileNotFoundError:
        return {}


def print_job(j):
    """display a job"""
    try:
        start = datetime.strptime(str(j["start_time"]), "%Y%m%dT%H:%M:%S")
        start = start.replace(tzinfo=timezone.utc)
        start_delta = datetime.now(timezone.utc) - start
    except ValueError:
        start_delta = "<starting>"

    print("\t\t", j["device"], "running job", j["id"], "for", start_delta)

    if "description" in j:
        d = j["description"]
        print(f"\t\t\t{d:<.55}")
    else:
        print("\t\t\t<no job name>")

    try:
        submit = datetime.strptime(str(j["submit_time"]), "%Y%m%dT%H:%M:%S")
        submit = submit.replace(tzinfo=timezone.utc)
        submit_delta = datetime.now(timezone.utc) - submit
    except ValueError:
        submit_delta = "?"

    s = j["submitter"]
    print(f"\t\t\tsubmitted {submit_delta} ago by {s}")


async def main():
    """main function"""
    labs = load_labs()

    config = read_config()

    lab_queries = []
    async with asyncio.TaskGroup() as tg:
        for l, d in labs.items():
            server = d["server"]
            lab_queries.append(tg.create_task(query_lab(l, server, config)))

    for l in lab_queries:
        for lab, device, active, bad, pending, jobs in l.result():
            print(lab, device)
            print(f"\t{pending} jobs pending, {active}/{active+bad} devices available")
            for j in jobs:
                print_job(j)


if __name__ == "__main__":
    asyncio.run(main())
