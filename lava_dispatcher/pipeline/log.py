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
import sys
import yaml
import zmq
import zmq.auth
from zmq.utils.strtypes import b


class ZMQPushHandler(logging.Handler):
    def __init__(self, logging_url, master_cert, slave_cert, job_id):
        super(ZMQPushHandler, self).__init__()

        # Create the PUSH socket
        # pylint: disable=no-member
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)

        # Load the certificates (if encryption is on)
        if master_cert is not None and slave_cert is not None:
            (client_public, client_private) = zmq.auth.load_certificate(slave_cert)
            self.socket.curve_publickey = client_public
            self.socket.curve_secretkey = client_private

            (server_public, _) = zmq.auth.load_certificate(master_cert)
            self.socket.curve_serverkey = server_public

        self.socket.connect(logging_url)

        self.job_id = str(job_id)
        self.action_level = '0'
        self.action_name = 'dispatcher'

        self.formatter = logging.Formatter("%(message)s")

    def setMetadata(self, level, name):
        self.action_level = level
        self.action_name = name

    def emit(self, record):
        msg = [b(self.job_id), b(self.action_level), b(self.action_name),
               b(self.formatter.format(record))]
        self.socket.send_multipart(msg)

    def close(self):
        super(ZMQPushHandler, self).close()
        self.socket.close()
        self.context.destroy()


class YAMLLogger(logging.Logger):
    def __init__(self, name):
        super(YAMLLogger, self).__init__(name)
        self.handler = None

    def addZMQHandler(self, logging_url, master_cert, slave_cert, job_id):
        self.handler = ZMQPushHandler(logging_url, master_cert,
                                      slave_cert, job_id)
        self.addHandler(self.handler)
        return self.handler

    def setMetadata(self, level, name):
        if isinstance(self.handler, ZMQPushHandler):
            self.handler.setMetadata(level, name)

    def log_message(self, level, level_name, message, *args, **kwargs):  # pylint: disable=unused-argument
        # Build the dictionnary
        data = {'dt': datetime.datetime.utcnow().isoformat(),
                'lvl': level_name}

        if isinstance(message, str) and args:
            data['msg'] = message % args
        else:
            data['msg'] = message
        # Set width to a really large value in order to always get one line.
        self._log(level, yaml.dump(data, default_flow_style=True,
                                   default_style='"',
                                   width=sys.maxsize)[:-1], ())

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

    def target(self, message, *args, **kwargs):
        self.log_message(logging.INFO, 'target', message, *args, **kwargs)

    def results(self, results, *args, **kwargs):
        self.log_message(logging.INFO, 'results', results, *args, **kwargs)
