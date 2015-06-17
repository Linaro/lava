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

import commands
import json
import logging
import pexpect
import time
import traceback
import hashlib
import signal
import simplejson
import subprocess
import sys
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

from lava_dispatcher.utils import kill_process_with_option

import lava_dispatcher.actions.lmp.init_boards as lmp_init_boards


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
        'device_group': {
            'type': 'array',
            'additionalProperties': False,
            'optional': True,
            'items': {
                'type': 'object',
                'properties': {
                    'role': {
                        'optional': False,
                        'type': 'string',
                    },
                    'count': {
                        'optional': False,
                        'type': 'integer',
                    },
                    'device_type': {
                        'optional': False,
                        'type': 'string',
                    },
                    'tags': {
                        'type': 'array',
                        'uniqueItems': True,
                        'items': {'type': 'string'},
                        'optional': True,
                    },
                    'is_slave': {
                        'optional': True,
                        'type': 'boolean',
                    },
                },
            },
        },
        'vm_group': {
            'type': 'object',
            'additionalProperties': False,
            'optional': True,
            'properties': {
                'host': {
                    'optional': False,
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'device_type': {
                            'optional': False,
                            'type': 'string',
                        },
                        'role': {
                            'optional': True,
                            'type': 'string',
                        }
                    }
                },
                'auto_start_vms': {
                    'type': 'boolean',
                    'optional': True,
                    'default': True,
                },
                'vms': {
                    'optional': False,
                    'type': 'array',
                    'additionalProperties': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'role': {
                                'optional': False,
                                'type': 'string',
                            },
                            'device_type': {
                                'optional': False,
                                'type': 'string',
                            },
                            'count': {
                                'optional': True,
                                'type': 'integer',
                            },
                            'launch_with': {
                                'type': 'string',
                                'optional': True,
                            },
                            'tags': {
                                'type': 'array',
                                'uniqueItems': True,
                                'items': {'type': 'string'},
                                'optional': True,
                            },
                        }

                    }
                },
            },
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
        'is_slave': {
            'type': 'boolean',
            'optional': True,
        },
        'lmp_module': {
            'optional': True,
            'type': 'array',
        },
        'is_vmhost': {
            'type': 'boolean',
            'default': False,
            'optional': True,
        },
        'auto_start_vms': {
            'type': 'boolean',
            'default': True,
            'optional': True,
        },
        'group_size': {
            'type': 'integer',
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
        except KeyError:
            return None

    def run(self, transport=None, group_data=None, vm_host_ip=None):
        if group_data:
            logging.debug("Group initialisation: %s" % json.dumps(group_data))
        self.context.assign_transport(transport)
        self.context.assign_group_data(group_data)
        validate_job_data(self.job_data)
        self._set_logging_level()
        lava_commands = get_all_cmds()
        lmp_init_data = []

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

        if 'target' in self.job_data:
            metadata['target'] = self.job_data['target']
            self.context.test_data.add_metadata(metadata)

        if 'logging_level' in self.job_data:
            metadata['logging_level'] = self.job_data['logging_level']
            self.context.test_data.add_metadata(metadata)

        if 'is_vmhost' in self.job_data:
            metadata['is_vmhost'] = "true" if self.job_data['is_vmhost'] else "false"
            metadata['host_ip'] = str(vm_host_ip)
            logging.debug("[ACTION-B] VM group test!")
            if not self.job_data['is_vmhost']:
                logging.debug("[ACTION-B] VM host IP is (%s)." % metadata['host_ip'])

            if 'auto_start_vms' in self.job_data:
                metadata['auto_start_vms'] = str(self.job_data['auto_start_vms']).lower()
            else:
                metadata['auto_start_vms'] = 'true'

            self.context.test_data.add_metadata(metadata)

        if 'target_group' in self.job_data:
            metadata['target_group'] = self.job_data['target_group']
            if 'is_slave' in self.job_data:
                metadata['is_slave'] = 'true' if self.job_data.get('is_slave') else 'false'
            self.context.test_data.add_metadata(metadata)

            if 'role' in self.job_data:
                metadata['role'] = self.job_data['role']
                self.context.test_data.add_metadata(metadata)

            if 'group_size' in self.job_data:
                metadata['group_size'] = self.job_data['group_size']
                self.context.test_data.add_metadata(metadata)

            logging.debug("[ACTION-B] Multi Node test!")
            logging.debug("[ACTION-B] target_group is (%s)." % self.context.test_data.metadata['target_group'])
        else:
            logging.debug("[ACTION-B] Single node test!")

        # get LMP init data, if it exists.
        if 'lmp_module' in self.job_data:
            lmp_init_data = self.job_data['lmp_module']
            metadata['lmp_module'] = json.dumps(lmp_init_data)
            self.context.test_data.add_metadata(metadata)
        # integrate LMP init data to LMP default config
        lmp_init_data = lmp_init_boards.data_integrate(lmp_init_data, self.context.device_config)
        # init LMP module, if necessary
        if lmp_init_data is not []:
            lmp_init_boards.init(lmp_init_data, self.context.device_config)

        def term_handler(signum, frame):
            self.context.finish()
            sys.exit(1)

        signal.signal(signal.SIGTERM, term_handler)

        try:
            job_length = len(self.job_data['actions'])
            job_num = 0
            for cmd in self.job_data['actions']:
                job_num += 1
                params = cmd.get('parameters', {})
                if cmd.get('command').startswith('lava_android_test'):
                    if not params.get('timeout') and \
                       self.job_data.get('timeout'):
                        params['timeout'] = self.job_data['timeout']
                logging.info("[ACTION-B] %s is started with %s" %
                             (cmd['command'], params))
                metadata = cmd.get('metadata', {})
                self.context.test_data.add_metadata(metadata)
                action = lava_commands[cmd['command']](self.context)
                err = None
                try:
                    status = 'fail'
                    action.run(**params)
                except ADBConnectError as err:
                    logging.info("ADBConnectError")
                    if cmd.get('command') == 'boot_linaro_android_image':
                        logging.warning(('[ACTION-E] %s failed to create the'
                                         ' adb connection') % (cmd['command']))

                        # Sometimes the adb problem is caused by the adb
                        # command, and as workround we need to kill the adb
                        # process to make it work
                        logging.warning(
                            'Now will try to kill the adb process')
                        rc = commands.getstatusoutput('adb devices')[0]
                        if rc != 0:
                            kill_process_with_option(process="adb",
                                                     key_option="fork-server")

                        # clear the session on the serial and wait a while
                        # and not put the following 3 sentences into the
                        # boot_linaro_android_image method just for
                        # avoiding effects when the method being called
                        # in other places
                        logging.warning(
                            'Now will reboot the image to try again')
                        self.context.client.proc.sendcontrol("c")
                        self.context.client.proc.sendline("")
                        time.sleep(5)
                        self.context.client.boot_linaro_android_image(
                            adb_check=True)
                        # mark it as pass if the second boot works
                        status = 'pass'
                except TimeoutError as err:
                    logging.info("TimeoutError")
                    if cmd.get('command').startswith('lava_android_test'):
                        logging.warning("[ACTION-E] %s times out." %
                                        (cmd['command']))
                        if job_num == job_length:
                            # not reboot the android image for
                            # the last test action
                            pass
                        else:
                            # clear the session on the serial and wait a while
                            # and not put the following 3 sentences into the
                            # boot_linaro_android_image method just for
                            # avoiding effects when the method being called
                            # in other places
                            logging.warning(
                                "Now the android image will be rebooted")
                            self.context.client.proc.sendcontrol("c")
                            self.context.client.proc.sendline("")
                            time.sleep(5)
                            self.context.client.boot_linaro_android_image()
                    else:
                        logging.warning("Unhandled timeout condition")
                        continue
                except CriticalError as err:
                    logging.info("CriticalError")
                    raise
                except (pexpect.TIMEOUT, GeneralError) as err:
                    logging.warning("pexpect timed out with status %s" % status)
                    pass
                except KeyboardInterrupt:
                    logging.info("Cancel operation")
                    err = "Cancel"
                    pass
                except subprocess.CalledProcessError as err:
                    if err.output is not None:
                        logging.info("Command error code: %d, with stdout/stderr:" % (err.returncode))
                        for line in err.output.rstrip('\n').split('\n'):
                            logging.info("| > %s" % (line))
                    else:
                        logging.info("Command error code: %d, without stdout/stderr" % (err.returncode))
                    raise

                except Exception as err:
                    logging.info("General Exception: %s" % unicode(str(err)))
                    raise
                else:
                    logging.debug("setting status pass")
                    status = 'pass'
                finally:
                    logging.debug("finally status %s" % status)
                    err_msg = ""
                    if status == 'fail':
                        # XXX mwhudson, 2013-01-17: I have no idea what this
                        # code is doing.
                        logging.warning(
                            "[ACTION-E] %s is finished with error (%s)." %
                            (cmd['command'], err))
                        err_msg = ("Lava failed at action %s with error:"
                                   "%s\n") % (cmd['command'],
                                              unicode(str(err),
                                                      'ascii', 'replace'))
                        if cmd['command'] == 'lava_test_run':
                            err_msg += "Lava failed on test: %s" % \
                                       params.get('test_name', "Unknown")
                        if err and err.message != "Cancel" and err.message != 'Timeout':
                            err_msg = err_msg + traceback.format_exc()
                            self.context.log("ErrorMessage: %s" % unicode(str(err)))
                        self.context.log(err_msg)
                    else:
                        logging.info(
                            "[ACTION-E] %s is finished successfully." %
                            (cmd['command']))
                        err_msg = ""
                    self.context.test_data.add_result(
                        action.test_name(**params), status, message=err_msg)
        except:
            # Capture all user-defined and non-user-defined critical errors
            self.context.test_data.job_status = 'fail'
            raise
        finally:
            self.context.finish()
            device_version = self.context.get_device_version() or 'error'
            self.context.test_data.add_metadata({
                'target.device_version': device_version
            })
            if 'target_group' in self.job_data:
                # all nodes call aggregate, even if there is no submit_results command
                self._aggregate_bundle(transport, lava_commands, submit_results)
            elif submit_results:
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

    def _aggregate_bundle(self, transport, lava_commands, submit_results):
        if "sub_id" not in self.job_data:
            raise ValueError("Invalid MultiNode JSON - missing sub_id")
        # all nodes call aggregate, even if there is no submit_results command
        base_msg = {
            "request": "aggregate",
            "bundle": None,
            "sub_id": self.job_data['sub_id']
        }
        if not submit_results:
            transport(json.dumps(base_msg))
            return
        # need to collate this bundle before submission, then send to the coordinator.
        params = submit_results.get('parameters', {})
        action = lava_commands[submit_results['command']](self.context)
        token = None
        group_name = self.job_data['target_group']
        if 'token' in params:
            token = params['token']
        # the transport layer knows the client_name for this bundle.
        bundle = action.collect_bundles(**params)
        # catch parse errors in bundles
        try:
            bundle_str = simplejson.dumps(bundle)
        except Exception as e:
            logging.error("Unable to parse bundle '%s' - %s" % (bundle, e))
            transport(json.dumps(base_msg))
            return
        sha1 = hashlib.sha1()
        sha1.update(bundle_str)
        base_msg['bundle'] = sha1.hexdigest()
        reply = transport(json.dumps(base_msg))
        # if this is sub_id zero, this will wait until the last call to aggregate
        # and then the reply is the full list of bundle checksums.
        if reply == "ack":
            # coordinator has our checksum for this bundle, submit as pending to launch_control
            action.submit_pending(bundle, params['server'], params['stream'], token, group_name)
            logging.info("Result bundle %s has been submitted to Dashboard as pending." % base_msg['bundle'])
            return
        elif reply == "nack":
            logging.error("Unable to submit result bundle checksum to coordinator")
            return
        else:
            if self.job_data["sub_id"].endswith(".0"):
                # submit this bundle, add it to the pending list which is indexed by group_name and post the set
                logging.info("Submitting bundle '%s' and aggregating with pending group results." % base_msg['bundle'])
                action.submit_group_list(bundle, params['server'], params['stream'], token, group_name)
                return
            else:
                raise ValueError("API error - collated bundle has been sent to the wrong node.")

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
