# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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

import json
import logging
import pexpect
import traceback

from linaro_json.schema import Schema, Validator

from lava_dispatcher.actions import get_all_cmds
from lava_dispatcher.client.base import CriticalError, GeneralError
from lava_dispatcher.config import get_config
from lava_dispatcher.context import LavaContext 


job_schema = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'actions': {
            'items': {
                'properties': {
                    'command': {
                        'optional': False,
                        },
                    'parameters': {
                        'optional': True,
                        },
                    'metadata': {
                        'optional': True,
                        },
                    },
                'additionalProperties': False,
                },
            },
        'device_type': {
            'optional': True,
            },
        'job_name': {
            'optional': True,
            },
        'image_type': {
            'optional': True,
            },
        'target': {
            'optional': True,
            },
        'timeout': {
            'type': 'integer',
            'optional': False,
            },
        'logging_level': {
            'optional': True,
            },
        },
    }

class LavaTestJob(object):
    def __init__(self, job_json, oob_file, config):
        self.job_status = 'pass'
        self.load_job_data(job_json)
        self.context = LavaContext(
            self.target, self.image_type, config, oob_file, self.job_data)

    def load_job_data(self, job_json):
        self.job_data = json.loads(job_json)

    @property
    def target(self):
        return self.job_data['target']

    @property
    def logging_level(self):
        try:
            return self.job_data['logging_level']
        except :
            return None

    @property
    def image_type(self):
        return self.job_data.get('image_type')

    def validate(self):
        schema = Schema(job_schema)
        validator = Validator()
        validator.validate(schema, self.job_data)

        lava_commands = get_all_cmds()
        for action in self.job_data['actions']:
            command_name = action['command']
            if command_name not in lava_commands:
                raise CriticalError("action %r not known" % command_name)

    def run(self):
        self.validate()
        self._set_logging_level()
        lava_commands = get_all_cmds()

        if self.job_data['actions'][-1]['command'].startswith("submit_results"):
            submit_results = self.job_data['actions'].pop(-1)
        else:
            submit_results = None

        metadata = {
            'target.hostname': self.target,
        }

        if 'device_type' in self.job_data:
            metadata['target.device_type'] = self.job_data['device_type']
        self.context.test_data.add_metadata(metadata)

        try:
            for cmd in self.job_data['actions']:
                params = cmd.get('parameters', {})
                logging.info("[ACTION-B] Command %s is started with parameters %s." % (cmd['command'],params))
                metadata = cmd.get('metadata', {})
                self.context.test_data.add_metadata(metadata)
                action = lava_commands[cmd['command']](self.context)
                try:
                    status = 'fail'
                    action.run(**params)
                except CriticalError as err:
                    raise
                except (pexpect.TIMEOUT, GeneralError) as err:
                    pass
                except Exception as err:
                    raise
                else:
                    status = 'pass'
                finally:
                    err_msg = ""
                    if status == 'fail':
                        logging.warning("[ACTION-E] %s is finished with error (%s)." %(cmd['command'], err))
                        err_msg = "Lava failed at action %s with error: %s\n" %\
                                  (cmd['command'], unicode(str(err), 'ascii', 'replace'))
                        if cmd['command'] == 'lava_test_run':
                            err_msg += "Lava failed on test: %s" %\
                                       params.get('test_name', "Unknown")
                        err_msg = err_msg + traceback.format_exc()
                        # output to both serial log and logfile
                        self.context.client.sio.write(err_msg)
                    else:
                        logging.info("[ACTION-E] %s is finished successfully." %cmd['command'])
                        err_msg = ""
                    self.context.test_data.add_result(
                        action.test_name(**params), status, err_msg)
        except:
            #Capture all user-defined and non-user-defined critical errors
            self.context.test_data.job_status='fail'
            raise
        finally:
            if submit_results:
                params = submit_results.get('parameters', {})
                action = lava_commands[submit_results['command']](
                    self.context)
                action.run(**params)

    def _set_logging_level(self):
        # set logging level is optional
        level = self.logging_level
        # CRITICAL, ERROR, WARNING, INFO or DEBUG
        if level:
            if level == 'DEBUG':
                logging.root.setLevel(logging.DEBUG)
            elif level == 'INFO':
                logging.root.setLevel(logging.INFO)
            elif level == 'WARNING':
                logging.root.setLevel(logging.WARNING)
            elif level == 'ERROR':
                logging.root.setLevel(logging.ERROR)
            elif level == 'CRITICAL':
                logging.root.setLevel(logging.CRITICAL)
            else:
                logging.warning("Unknown logging level in the job '%s'. Allow level are : CRITICAL, ERROR, WARNING, INFO or DEBUG" %level)
