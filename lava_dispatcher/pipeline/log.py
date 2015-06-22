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


class ZMQPushHandler(logging.Handler):
    def __init__(self, socket_addr, job_id):
        super(ZMQPushHandler, self).__init__()

        # Create the PUSH socket
        # pylint: disable=no-member
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect(socket_addr)

        self.job_id = str(job_id)
        self.action_level = '0'
        self.action_name = 'dispatcher'

        self.formatter = logging.Formatter("%(message)s")

    def setMetadata(self, level, name):
        self.action_level = level
        self.action_name = name

    def emit(self, record):
        msg = [self.job_id, self.action_level, self.action_name,
               self.formatter.format(record)]
        self.socket.send_multipart(msg)

    def close(self):
        super(ZMQPushHandler, self).close()
        self.socket.close()
        self.context.destroy()


class YAMLLogger(logging.Logger):
    def __init__(self, name):
        super(YAMLLogger, self).__init__(name)
        self.handler = None

    def addZMQHandler(self, socket_addr, job_id):
        self.handler = ZMQPushHandler(socket_addr, job_id)
        self.addHandler(self.handler)
        return self.handler

    def setMetadata(self, level, name):
        if isinstance(self.handler, ZMQPushHandler):
            self.handler.setMetadata(level, name)

    def log_message(self, level, level_name, message, *args, **kwargs):
        # If the received message is a dictionary then we look for specific log
        # parameters such as timestamp, else we assume the log message is a
        # string and dump the message.
        if isinstance(message, dict) and 'ts' in message:
            self._log(level, yaml.dump([{'ts': message['ts'],
                                         level_name: message['msg']}])[:-1],
                      args, kwargs)
        else:
            self._log(level, yaml.dump([{level_name: message}])[:-1], args,
                      kwargs)

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


class StdLogger(object):  # pylint: disable=too-few-public-methods

    def __init__(self, name, filename):
        """
        Output for stdout (which is redirected to the oob_file by the
        scheduler) should use the ASCII logger.
        """
        self.name = name
        self.description = "std logger"
        self.log = logging.getLogger("%s" % name)
        self.log.setLevel(logging.INFO)
        self.handler = logging.StreamHandler(filename)
        self.formatter = logging.Formatter('"%(asctime)s":\n - %(message)s')
        self.handler.setFormatter(self.formatter)

    def info(self, message):
        self.log.info(message)

    def debug(self, message):
        self.log.debug(message)
