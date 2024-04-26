# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import decimal
import logging

from lava_common.exceptions import LAVABug, TestError
from lava_common.timeout import Timeout
from lava_dispatcher.action import InternalObject

RECOGNIZED_TAGS = ("telnet", "ssh", "shell")


class SignalMatch(InternalObject):
    def match(self, data, fixupdict=None):
        if not fixupdict:
            fixupdict = {}

        res = {}
        for key in data:
            # Special cases for 'measurement'
            if key == "measurement":
                try:
                    measurement = decimal.Decimal(data["measurement"])
                except decimal.InvalidOperation:
                    raise TestError("Invalid measurement %s" % data["measurement"])
                res["measurement"] = float(measurement)

            # and 'result'
            elif key == "result":
                res["result"] = data["result"]
                if data["result"] in fixupdict:
                    res["result"] = fixupdict[data["result"]]
                if res["result"] not in ("pass", "fail", "skip", "unknown"):
                    res["result"] = "unknown"
                    raise TestError("Bad test result: %s" % data["result"])

            # or just copy the data
            else:
                res[key] = data[key]

        if "test_case_id" not in res:
            raise TestError(
                "Test case results without test_case_id (probably a sign of an "
                "incorrect parsing pattern being used): %s" % res
            )

        if "result" not in res:
            res["result"] = "unknown"
            raise TestError(
                "Test case results without result (probably a sign of an "
                "incorrect parsing pattern being used): %s" % res
            )

        return res


class Protocol:
    """
    Similar to a Connection object, provides a transport layer for the dispatcher.
    Uses a pre-defined API instead of pexpect using Shell.

    Testing a protocol involves either basing the protocol on SocketServer and using threading
    or adding a main function in the protocol python file and including a demo server script which
    can be run on the command line - using a different port to the default. However, this is likely
    to be of limited use because testing the actual API calls will need a functional test.

    If a Protocol requires another Protocol to be available in order to run, the depending
    Protocol *must* specify a higher level. All Protocol objects of a lower level are setup and
    run before Protocol objects of a higher level. Protocols with the same level can be setup or run
    in an arbitrary order (as the original source data is a dictionary).
    """

    name = "protocol"
    level = 0

    def __init__(self, parameters, job_id):
        self.logger = logging.getLogger("dispatcher")
        self.poll_timeout = Timeout(self.name, None)
        self.__errors__ = []
        self.parameters = parameters
        self.configured = False
        self.job_id = job_id

    @classmethod
    def select_all(cls, parameters):
        """
        Multiple protocols can apply to the same job, each with their own parameters.
        Jobs may have zero or more protocols selected.
        """
        candidates = cls.__subclasses__()
        return [(c, c.level) for c in candidates if c.accepts(parameters)]

    @property
    def errors(self):
        return self.__errors__

    @errors.setter
    def errors(self, error):
        self.__errors__.append(error)

    @property
    def valid(self):
        return not bool([x for x in self.errors if x])

    def set_up(self):
        raise LAVABug("'set_up' not implemented")

    def configure(self, device, job):
        self.configured = True

    def finalise_protocol(self, device=None):
        raise LAVABug("'finalise_protocol' not implemented")

    def set_timeout(self, duration):
        self.poll_timeout.duration = duration

    def check_timeout(self, duration, data):
        """
        Use if particular protocol calls can require a connection timeout
        larger than the default_connection_duration.
        :param duration: A minimum number of seconds
        :param data: the API call
        :return: True if checked, False if no limit is specified by the protocol.
        raises JobError if the API call is invalid.
        """
        return False

    def _api_select(self, data, action=None):
        if not data:
            return None
        raise LAVABug("'_api_select' not implemented")

    def __call__(self, *args, **kwargs):
        """Makes the Protocol callable so that actions can send messages just using the protocol.
        This function may block until the specified API call returns. Some API calls may involve a
        substantial period of polling.
        :param args: arguments of the API call to make
        :return: A Python object containing the reply dict from the API call
        """
        # implementations will usually need a try: except: block around _api.select()
        return self._api_select(args, action=None)

    def collate(self, reply_dict, params_dict):
        return None
