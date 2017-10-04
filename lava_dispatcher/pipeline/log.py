# Copyright (C) 2014 Linaro Limited
#
# Author: Senthil Kumaran S <senthil.kumaran@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import datetime
import logging
import yaml
import zmq
import zmq.auth
from zmq.utils.strtypes import b


class ZMQPushHandler(logging.Handler):
    def __init__(self, logging_url, master_cert, slave_cert, job_id, ipv6):
        super(ZMQPushHandler, self).__init__()

        # Keep track of the parameters
        self.logging_url = logging_url
        self.master_cert = master_cert
        self.slave_cert = slave_cert
        self.ipv6 = ipv6

        # Create the PUSH socket
        # pylint: disable=no-member
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)

        if ipv6:
            self.socket.setsockopt(zmq.IPV6, 1)

        # Load the certificates (if encryption is on)
        if master_cert is not None and slave_cert is not None:
            (client_public, client_private) = zmq.auth.load_certificate(slave_cert)
            self.socket.curve_publickey = client_public
            self.socket.curve_secretkey = client_private

            (server_public, _) = zmq.auth.load_certificate(master_cert)
            self.socket.curve_serverkey = server_public

        self.socket.connect(logging_url)

        self.job_id = str(job_id)
        self.formatter = logging.Formatter("%(message)s")

    def emit(self, record):
        msg = [b(self.job_id), b(self.formatter.format(record))]
        self.socket.send_multipart(msg)

    def close(self, linger):
        super(ZMQPushHandler, self).close()
        self.context.destroy(linger=linger)


class YAMLLogger(logging.Logger):
    def __init__(self, name):
        super(YAMLLogger, self).__init__(name)
        self.handler = None

    def addZMQHandler(self, logging_url, master_cert, slave_cert, job_id, ipv6):
        self.handler = ZMQPushHandler(logging_url, master_cert,
                                      slave_cert, job_id, ipv6)
        self.addHandler(self.handler)
        return self.handler

    def close(self, linger=-1):
        if self.handler is not None:
            self.handler.close(linger)
            self.removeHandler(self.handler)
            self.handler = None

    def log_message(self, level, level_name, message, *args, **kwargs):  # pylint: disable=unused-argument
        # Build the dictionnary
        data = {'dt': datetime.datetime.utcnow().isoformat(),
                'lvl': level_name}

        if isinstance(message, str) and args:
            data['msg'] = message % args
        else:
            data['msg'] = message

        # Set width to a really large value in order to always get one line.
        # But keep this reasonable because the logs will be loaded by CLoader
        # that is limited to around 10**7 chars
        data_str = yaml.dump(data, default_flow_style=True,
                             default_style='"',
                             width=10 ** 6,
                             Dumper=yaml.CDumper)[:-1]
        # Test the limit and skip if the line is too long
        if len(data_str) >= 10 ** 6:
            if isinstance(message, str):
                data['msg'] = "<line way too long ...>"
            else:
                data['msg'] = {"skip": "line way too long ..."}
            data_str = yaml.dump(data, default_flow_style=True,
                                 default_style='"',
                                 width=10 ** 6,
                                 Dumper=yaml.CDumper)[:-1]
        self._log(level, data_str, ())

    def exception(self, exc, *args, **kwargs):
        self.log_message(logging.ERROR, 'exception', exc, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self.log_message(logging.ERROR, 'error', message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self.log_message(logging.WARNING, 'warning', message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self.log_message(logging.INFO, 'info', message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        self.log_message(logging.DEBUG, 'debug', message, *args, **kwargs)

    def input(self, message, *args, **kwargs):
        self.log_message(logging.INFO, 'input', message, *args, **kwargs)

    def target(self, message, *args, **kwargs):
        self.log_message(logging.INFO, 'target', message, *args, **kwargs)

    def feedback(self, message, *args, **kwargs):
        self.log_message(logging.INFO, 'feedback', message, *args, **kwargs)

    def results(self, results, *args, **kwargs):
        if 'extra' in results and 'level' not in results:
            raise Exception("'level' is mandatory when 'extra' is used")
        self.log_message(logging.INFO, 'results', results, *args, **kwargs)
