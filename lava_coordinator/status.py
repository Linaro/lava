#! /usr/bin/env python

"""
Status check for lava-coordinator
"""

#  Copyright 2015 Linaro Limited
#  Author Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import errno
import json
import os
import socket
import sys
import time
from socket import gethostname

HOST = "localhost"  # The coordinator hostname default


def read_settings(filename):
    """
    NodeDispatchers need to use the same port and blocksize as the Coordinator,
    so read the same conffile.
    """
    settings = {
        "port": 3079,
        "coordinator_hostname": "localhost",
        "blocksize": 4 * 1024,
    }
    if not os.path.exists(filename):
        # unknown as there is no usable configuration
        print("No lava-coordinator configuration file found!")
        sys.exit(3)
    with open(filename) as stream:
        jobdata = stream.read()
        json_default = json.loads(jobdata)
    if "port" in json_default:
        settings["port"] = json_default["port"]
    if "blocksize" in json_default:
        settings["blocksize"] = json_default["blocksize"]
    if "coordinator_hostname" in json_default:
        settings["coordinator_hostname"] = json_default["coordinator_hostname"]
    return settings


def lava_poll(port, host, name, request):
    """
    Modified poll equivalent
    """
    errors = []
    warnings = []
    while True:
        sock = None
        count = 0
        while count < 5:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
                sock.connect((host, port))
                break
            except OSError as exc:
                if exc.errno == errno.ECONNRESET:
                    warnings.append("connection reset by peer: bug 1020")
                errors.append("not connected, sleeping for 1 second")
                time.sleep(1)
                sock = None
                count += 1
                warnings.append("retrying port %s on %s" % (port, host))
        if count >= 5:
            break
        msg = {
            "group_name": "group1",
            "group_size": 2,
            "hostname": gethostname(),
            "role": "client",
            "client_name": name,
            "request": request,
            "message": None,
        }
        msg_str = json.dumps(msg)
        msg_len = len(msg_str)
        try:
            # send the length as 32bit hexadecimal
            ret_bytes = sock.send(b"%08X" % msg_len)
            if ret_bytes == 0:
                warnings.append("zero bytes sent for length - connection closed?")
                continue
            ret_bytes = sock.send(msg_str.encode("utf-8"))
            if ret_bytes == 0:
                warnings.append("zero bytes sent for message - connection closed?")
                continue
        except OSError as exc:
            errors.append("socket error '%d' on send" % exc.message)
            sock.close()
            continue
        try:
            data = str(sock.recv(8))  # 32bit limit
            data = sock.recv(1024)
        except OSError as exc:
            errors.append("Exception on receive: %s" % exc)
            continue
        try:
            json_data = json.loads(data.decode("utf-8"))
        except ValueError:
            warnings.append("data not JSON %s" % data)
            break
        if "response" not in json_data:
            errors.append("no response field in data")
            break
        if json_data["response"] != "wait":
            break
        else:
            break
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
    ret = 0
    if errors:
        ret = 2
    elif warnings:
        ret = 1
    if errors or warnings:
        print("Using python%s" % sys.version_info[0])
        print("E:%s W:%s" % (errors, warnings))
        return ret
    else:
        return ret


def main():
    """Run a simple check on the API"""
    port = 3079  # The same port as used by the server
    host = "localhost"
    conffile = "/etc/lava-coordinator/lava-coordinator.conf"
    settings = read_settings(conffile)
    port = settings["port"]
    host = settings["coordinator_hostname"]
    ret1 = lava_poll(port, host, "status", "group_data")
    ret2 = lava_poll(port, host, "status", "clear_group")
    if not ret1 and not ret2:
        print("Using python%s" % sys.version_info[0])
        print("status check complete. No errors")
    if ret1 and ret1 >= ret2:
        sys.exit(ret1)
    if ret2:
        sys.exit(ret2)


if __name__ == "__main__":
    main()
