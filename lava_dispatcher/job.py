# Copyright (C) 2011-2012 Linaro Limited
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
import time
import traceback

from json_schema_validator.schema import Schema
from json_schema_validator.validator import Validator

from lava_dispatcher.actions import get_all_cmds
from lava_dispatcher.context import LavaContext
from lava_dispatcher.errors import (
    CriticalError,
    TimeoutError,
    GeneralError,
    ADBConnectError,
)


job_schema = {
    'type': 'object',
    'additionalProperties': {},
    'properties': {
        'actions': {
            'items': {
                'type': 'object',
                'properties': {
                    'command': {
                        'optional': False,
                        'type': 'string',
                        },
                    'parameters': {
                        'optional': True,
                        'type': 'object',
                        },
                    'metadata': {
                        'optional': True,
                        },
                    },
                'additionalProperties': False,
                },
            },
        'device_type': {
            'type': 'string',
            'optional': True,
            },
        'job_name': {
            'type': 'string',
            'optional': True,
            },
        'health_check': {
            'optional': True,
            'default': False,
            },
        'target': {
            'type': 'string',
            'optional': True,
            },
        'target_group': {
            'type': 'string',
            'optional': True,
        },
        'port': {
            'type': 'integer',
            'optional': True,
        },
        'hostname': {
            'type': 'string',
            'optional': True,
        },
        'role': {
            'type': 'string',
            'optional': True,
        },
        'group_size': {
            'type': 'string',
            'optional': True,
        },
        'timeout': {
            'type': 'integer',
            'optional': False,
            },
        'logging_level': {
            'type': 'string',
            'enum': ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
            'optional': True,
            },
        'tags': {
            'type': 'array',
            'uniqueItems': True,
            'items': {'type': 'string'},
            'optional': True,
            },
        'priority': {
            'type': 'string',
            'optional': True,
            },
        },
    }


def validate_job_data(job_data):
    schema = Schema(job_schema)
    Validator.validate(schema, job_data)
    lava_commands = get_all_cmds()
    for action in job_data['actions']:
        command_name = action['command']
        command = lava_commands.get(command_name)
        if command is None:
            raise ValueError("action %r not known" % command_name)
        command.validate_parameters(action.get('parameters'))


class LavaTestJob(object):
    def __init__(self, job_json, oob_file, config, output_dir):
        self.job_status = 'pass'
        self.load_job_data(job_json)
        self.context = LavaContext(
            self.target, config, oob_file, self.job_data, output_dir)

    def load_job_data(self, job_json):
        self.job_data = json.loads(job_json)

    @property
    def target(self):
        return self.job_data['target']

    @property
    def tags(self):
        return self.job_data.get('tags', [])

    @property
    def logging_level(self):
        try:
            return self.job_data['logging_level']
        except:
            return None

    def run(self, transport=None):
        self.transport = transport
        validate_job_data(self.job_data)
        self._set_logging_level()
        lava_commands = get_all_cmds()
        # prototype for the NodeDispatcher call to be used later in lava_test_shell.
        if self.transport:
            from lava.dispatcher.node import NodeDispatcher
            self.transport("foo")

        if self.job_data['actions'][-1]['command'].startswith(
            "submit_results"):
            submit_results = self.job_data['actions'].pop(-1)
        else:
            submit_results = None

        metadata = {
            'target.hostname': self.target,
        }

        if 'device_type' in self.job_data:
            metadata['target.device_type'] = self.job_data['device_type']
        self.context.test_data.add_metadata(metadata)

        self.context.test_data.add_tags(self.tags)

        try:
            job_length = len(self.job_data['actions'])
            job_num = 0
            for cmd in self.job_data['actions']:
                job_num = job_num + 1
                params = cmd.get('parameters', {})
                if cmd.get('command').startswith('lava_android_test'):
                    if not params.get('timeout') and \
                       self.job_data.get('timeout'):
                        params['timeout'] = self.job_data['timeout']
                logging.info("[ACTION-B] %s is started with %s" % (
                                            cmd['command'], params))
                metadata = cmd.get('metadata', {})
                self.context.test_data.add_metadata(metadata)
                action = lava_commands[cmd['command']](self.context)
                err = None
                try:
                    status = 'fail'
                    action.run(**params)
                except ADBConnectError:
                    if cmd.get('command') == 'boot_linaro_android_image':
                        logging.warning(('[ACTION-E] %s failed to create the'
                                         ' adb connection') % (cmd['command']))
                        ## clear the session on the serial and wait a while
                        ## and not put the following 3 sentences into the
                        ## boot_linaro_android_image method just for
                        ## avoiding effects when the method being called
                        ## in other places
                        logging.warning(
                            'Now will reboot the image to try again')
                        self.context.client.proc.sendcontrol("c")
                        self.context.client.proc.sendline("")
                        time.sleep(5)
                        self.context.client.boot_linaro_android_image(
                            adb_check=True)
                        ## mark it as pass if the second boot works
                        status = 'pass'
                except TimeoutError as err:
                    if cmd.get('command').startswith('lava_android_test'):
                        logging.warning("[ACTION-E] %s times out." % (
                                                cmd['command']))
                        if job_num == job_length:
                            ## not reboot the android image for
                            ## the last test action
                            pass
                        else:
                            ## clear the session on the serial and wait a while
                            ## and not put the following 3 sentences into the
                            ## boot_linaro_android_image method just for
                            ## avoiding effects when the method being called
                            ## in other places
                            logging.warning(
                                "Now the android image will be rebooted")
                            self.context.client.proc.sendcontrol("c")
                            self.context.client.proc.sendline("")
                            time.sleep(5)
                            self.context.client.boot_linaro_android_image()
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
                        # XXX mwhudson, 2013-01-17: I have no idea what this
                        # code is doing.
                        logging.warning(
                            "[ACTION-E] %s is finished with error (%s)." % (
                                    cmd['command'], err))
                        err_msg = ("Lava failed at action %s with error:"
                                   "%s\n") % (cmd['command'],
                                              unicode(str(err),
                                                      'ascii', 'replace'))
                        if cmd['command'] == 'lava_test_run':
                            err_msg += "Lava failed on test: %s" % \
                                       params.get('test_name', "Unknown")
                        err_msg = err_msg + traceback.format_exc()
                        print err_msg
                    else:
                        logging.info(
                            "[ACTION-E] %s is finished successfully." % (
                                                        cmd['command']))
                        err_msg = ""
                    self.context.test_data.add_result(
                        action.test_name(**params), status, err_msg)
        except:
            #Capture all user-defined and non-user-defined critical errors
            self.context.test_data.job_status = 'fail'
            raise
        finally:
            device_version = self.context.get_device_version() or 'error'
            self.context.test_data.add_metadata({
                'target.device_version': device_version
            })
            if submit_results:
                params = submit_results.get('parameters', {})
                action = lava_commands[submit_results['command']](
                    self.context)
                params_for_display = params.copy()
                if 'token' in params_for_display:
                    params_for_display['token'] = '<HIDDEN>'
                try:
                    logging.info("Submitting the test result with parameters = %s", params_for_display)
                    action.run(**params)
                except Exception as err:
                    logging.error("Failed to submit the test result. Error = %s", err)
                    raise

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
                logging.warning("Unknown logging level in the job '%s'. "
                                "Allow level are : CRITICAL, ERROR, "
                                "WARNING, INFO or DEBUG" % level)
