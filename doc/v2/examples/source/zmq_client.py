#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zmq_client.py script
"""
#  Copyright 2018 Linaro
#  Author: Neil Williams <neil.williams@linaro.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.


# START_CLIENT

import sys
import ssl
import argparse
import yaml
import signal
import zmq
import xmlrpc.client
from urllib.parse import urlsplit


FINISHED_JOB_STATUS = ["Complete", "Incomplete", "Canceled"]


class JobEndTimeoutError(Exception):
    """ Raise when the specified job does not finish in certain timeframe. """


class Timeout:
    """ Timeout error class with ALARM signal. Accepts time in seconds. """

    class TimeoutError(Exception):
        pass

    def __init__(self, sec=0):
        self.sec = sec

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.timeout_raise)
        if not self.sec:
            self.sec = 0
        signal.alarm(self.sec)

    def __exit__(self, *args):
        signal.alarm(0)

    def timeout_raise(self, *args):
        raise Timeout.TimeoutError()


class JobListener:
    def __init__(self, url):
        self.context = zmq.Context.instance()
        self.sock = self.context.socket(zmq.SUB)

        self.sock.setsockopt(zmq.SUBSCRIBE, b"")
        self.sock.connect(url)

    def wait_for_job_end(self, job_id, timeout=None):

        try:
            with Timeout(timeout):
                while True:
                    msg = self.sock.recv_multipart()
                    try:
                        (topic, uuid, dt, username, data) = msg[:]
                    except IndexError:
                        # Dropping invalid message
                        continue

                    data = yaml.safe_load(data)
                    if "job" in data:
                        if data["job"] == job_id:
                            if data["health"] in FINISHED_JOB_STATUS:
                                return data

        except Timeout.TimeoutError:
            raise JobEndTimeoutError(
                "JobListener timed out after %s seconds." % timeout
            )


def lookup_publisher(hostname, https):
    """
    Lookup the publisher details using XML-RPC
    on the specified hostname.
    """
    xmlrpc_url = "http://%s/RPC2" % (hostname)
    if https:
        xmlrpc_url = "https://%s/RPC2" % (hostname)
    server = xmlrpc.client.ServerProxy(xmlrpc_url)
    try:
        socket = server.scheduler.get_publisher_event_socket()
    except ssl.SSLError as exc:
        sys.stderr.write("ERROR %s\n" % exc)
        return None
    port = urlsplit(socket).port
    listener_url = "tcp://%s:%s" % (hostname, port)
    print("Using %s" % listener_url)
    return listener_url


def main():
    """
    Parse the command line
    For simplicity, this script does not handle usernames
    and tokens so needs a job ID. For support submitting
    a test job as well as watching the events, use lavacli.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", "--job-id", type=int, help="Job ID to wait for")

    parser.add_argument(
        "--https", action="store_true", help="Use https:// for this hostname"
    )

    parser.add_argument("-t", "--timeout", type=int, help="Timeout in seconds")
    parser.add_argument("--hostname", required=True, help="hostname of the instance")

    options = parser.parse_args()

    try:
        publisher = lookup_publisher(options.hostname, options.https)
    except xmlrpc.client.ProtocolError as exc:
        sys.stderr.write("ERROR %s\n" % exc)
        return 1

    if not publisher:
        return 1

    if options.job_id:
        listener = JobListener(publisher)
        print(listener.wait_for_job_end(options.job_id, options.timeout))
    print("\n")
    return 0


if __name__ == "__main__":
    main()

# END_CLIENT
