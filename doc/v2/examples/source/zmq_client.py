# START_CLIENT

import argparse
import yaml
import logging
import re
import signal
import time
import zmq
from zmq.utils.strtypes import b, u


FINISHED_JOB_STATUS = ["Complete", "Incomplete", "Canceled"]


class JobEndTimeoutError(Exception):
    """ Raise when the specified job does not finish in certain timeframe. """


class Timeout():
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


class JobListener():

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


def main():
    # Parse the command line
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--publisher", default="tcp://127.0.0.1:5500",
                        help="Publisher host and port")
    parser.add_argument("-j", "--job-id", type=int,
                        help="Job ID to wait for")
    parser.add_argument("-t", "--timeout", type=int,
                        help="Timeout in seconds")

    options = parser.parse_args()

    listener = JobListener(options.publisher)
    print listener.wait_for_job_end(options.job_id, options.timeout)


if __name__ == '__main__':
    main()

# END_CLIENT
