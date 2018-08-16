"""
zmq_client.py script
"""
# pylint: disable=missing-docstring,no-member,unused-variable,too-few-public-methods
# pylint: disable=invalid-name,unused-argument,no-self-use,wrong-import-order
# START_CLIENT

import argparse
import yaml
import signal
import zmq
import xmlrpclib
from urlparse import urlsplit


FINISHED_JOB_STATUS = ["Complete", "Incomplete", "Canceled"]


class JobEndTimeoutError(Exception):
    """ Raise when the specified job does not finish in certain timeframe. """


class Timeout:
    """ Timeout error class with ALARM signal. Accepts time in seconds. """
    class TimeoutError(Exception):
        pass

    def __init__(self, sec):
        self.sec = sec

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.timeout_raise)
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
                        # Droping invalid message
                        continue

                    data = yaml.safe_load(data)
                    if "job" in data:
                        if data["job"] == job_id:
                            if data["status"] in FINISHED_JOB_STATUS:
                                return data

        except Timeout.TimeoutError:
            raise JobEndTimeoutError(
                "JobListener timed out after %s seconds." % timeout)


def lookup_publisher(hostname):
    """
    Lookup the publisher details using XML-RPC
    on the specified hostname.
    """
    xmlrpc_url = "http://%s/RPC2" % (hostname)
    server = xmlrpclib.ServerProxy(xmlrpc_url)
    socket = server.scheduler.get_publisher_event_socket()
    port = urlsplit(socket).port
    listener_url = 'tcp://%s:%s' % (hostname, port)
    print("Using %s" % listener_url)
    return listener_url


def main():
    """
    Parse the command line
    For simplicity, this script does not handle usernames
    and tokens so needs a job ID. For support submitting
    a test job as well as watching the events, use lava-tool.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", "--job-id", type=int,
                        help="Job ID to wait for")

    parser.add_argument("-t", "--timeout", type=int,
                        help="Timeout in seconds")
    parser.add_argument("--hostname", help="hostname of the instance")

    options = parser.parse_args()

    publisher = lookup_publisher(options.hostname)

    listener = JobListener(publisher)
    print listener.wait_for_job_end(options.job_id, options.timeout)
    print('\n')


if __name__ == '__main__':
    main()

# END_CLIENT
