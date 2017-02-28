# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import atexit
import logging
import errno
import signal
import shutil
import tempfile
import time
import traceback
import os
import yaml

from lava_dispatcher.pipeline.action import (
    LAVABug,
    LAVAError,
    JobError,
)
from lava_dispatcher.pipeline.log import YAMLLogger  # pylint: disable=unused-import
from lava_dispatcher.pipeline.logical import PipelineContext
from lava_dispatcher.pipeline.diagnostics import DiagnoseNetwork
from lava_dispatcher.pipeline.protocols.multinode import MultinodeProtocol  # pylint: disable=unused-import
from lava_dispatcher.pipeline.utils.constants import DISPATCHER_DOWNLOAD_DIR
from lava_dispatcher.pipeline.utils.filesystem import debian_package_version


class ZMQConfig(object):
    """
    Namespace for the ZMQ logging configuration
    """
    def __init__(self, logging_url, master_cert, slave_cert):
        self.logging_url = logging_url
        self.master_cert = master_cert
        self.slave_cert = slave_cert


class Job(object):  # pylint: disable=too-many-instance-attributes
    """
    Populated by the parser, the Job contains all of the
    Actions and their pipelines.
    parameters provides the immutable data about this job:
        action_timeout
        job_name
        priority
        device_type (mapped to target by scheduler)
        yaml_line
        logging_level
        job_timeout
    Job also provides the primary access to the Device.
    The NewDevice class only loads the specific configuration of the
    device for this job - one job, one device.
    """

    def __init__(self, job_id, parameters, zmq_config):  # pylint: disable=too-many-arguments
        self.job_id = job_id
        self.zmq_config = zmq_config
        self.device = None
        self.parameters = parameters
        self.__context__ = PipelineContext()
        self.pipeline = None
        self.connection = None
        self.triggers = []  # actions can add trigger strings to the run a diagnostic
        self.diagnostics = [
            DiagnoseNetwork,
        ]
        self.timeout = None
        self.protocols = []
        self.compatibility = 2
        # Was the job cleaned
        self.cleaned = False
        # Root directory for the job tempfiles
        self.tmp_dir = None
        # override in use
        self.base_overrides = {}

    @property
    def context(self):
        return self.__context__.pipeline_data

    @context.setter
    def context(self, data):
        self.__context__.pipeline_data.update(data)

    def diagnose(self, trigger):
        """
        Looks up the class to execute to diagnose the problem described by the
         specified trigger.
        """
        trigger_tuples = [(cls.trigger(), cls) for cls in self.diagnostics]
        for diagnostic in trigger_tuples:
            if trigger is diagnostic[0]:
                return diagnostic[1]()
        return None

    def describe(self):
        return {'device': self.device,
                'job': self.parameters,
                'compatibility': self.compatibility,
                'pipeline': self.pipeline.describe()}

    def setup_logging(self):
        # We are now able to create the logger when the job is started,
        # allowing the functions that are called before run() to log.
        # The validate() function is no longer called on the master so we can
        # safelly add the ZMQ handler. This way validate can log errors that
        # test writter will see.
        self.logger = logging.getLogger('dispatcher')
        if self.zmq_config is not None:
            # pylint: disable=no-member
            self.logger.addZMQHandler(self.zmq_config.logging_url,
                                      self.zmq_config.master_cert,
                                      self.zmq_config.slave_cert,
                                      self.job_id)
            self.logger.setMetadata("0", "validate")
        else:
            self.logger.addHandler(logging.StreamHandler())

    def mkdtemp(self, action_name, override=None):
        """
        Create a tmp directory in DISPATCHER_DOWNLOAD_DIR/{job_id}/ because
        this directory will be removed when the job finished, making cleanup
        easier.
        """
        if override is None:
            if self.tmp_dir is None:
                create_base_dir = True
                base_dir = DISPATCHER_DOWNLOAD_DIR
            else:
                create_base_dir = False
                base_dir = self.tmp_dir
        else:
            if override in self.base_overrides:
                create_base_dir = False
                base_dir = self.base_overrides[override]
            else:
                create_base_dir = True
                base_dir = override

        if create_base_dir:
            # Try to create the directory.
            base_dir = os.path.join(base_dir, str(self.job_id))
            try:
                os.makedirs(base_dir, mode=0o755)
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    # When running unit tests
                    base_dir = tempfile.mkdtemp(prefix='pipeline-')
                    atexit.register(shutil.rmtree, base_dir, ignore_errors=True)
            # Save the path for the next calls (only if that's not an override)
            if override is None:
                self.tmp_dir = base_dir
            else:
                self.base_overrides[override] = base_dir

        # Create the sub-directory
        tmp_dir = tempfile.mkdtemp(prefix=action_name + '-', dir=base_dir)
        os.chmod(tmp_dir, 0o755)
        return tmp_dir

    def _validate(self, simulate):
        """
        Validate the pipeline and raise an exception (that inherit from
        LAVAError) if it fails.
        If simulate is True, then print the pipeline description.
        """
        label = "lava-dispatcher, installed at version: %s" % debian_package_version()
        self.logger.info(label)
        self.logger.info("start: 0 validate")
        start = time.time()

        for protocol in self.protocols:
            try:
                protocol.configure(self.device, self)
            except KeyboardInterrupt:
                self.logger.info("Canceled")
                raise JobError("Canceled")
            except LAVAError:
                raise
            except Exception as exc:
                self.logger.error("Protocol configuration failed")
                self.logger.exception(traceback.format_exc())
                raise LAVABug(exc)

            if not protocol.valid:
                msg = "protocol %s has errors: %s" % (protocol.name, protocol.errors)
                self.logger.exception(msg)
                raise JobError(msg)

        if simulate:
            # output the content and then any validation errors (python3 compatible)
            print(yaml.dump(self.describe()))  # pylint: disable=superfluous-parens

        try:
            self.pipeline.validate_actions()
        except KeyboardInterrupt:
            self.logger.info("Canceled")
            raise JobError("Canceled")
        except LAVAError as exc:
            self.logger.error("Invalid job definition")
            self.logger.exception(str(exc))
            # This should be re-raised to end the job
            raise
        except Exception as exc:
            self.logger.error("Validation failed")
            self.logger.exception(traceback.format_exc())
            raise LAVABug(exc)
        finally:
            self.logger.info("validate duration: %.02f", time.time() - start)

    def validate(self, simulate=False):
        """
        Public wrapper for the pipeline validation.
        Send a "fail" results if needed.
        """
        try:
            self._validate(simulate)
        except LAVAError as exc:
            self.cleanup(connection=None)
            self.logger.results({"definition": "lava",
                                 "case": "job",
                                 "result": "fail"})
            self.logger.error(exc.error_msg)
            raise

    def cancelling_handler(*_):
        """
        Catches KeyboardInterrupt or SIGTERM and raise
        KeyboardInterrupt that will go through all the stack frames. We then
        cleanup the job and report the errors.
        """
        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, signal.default_int_handler)
        raise KeyboardInterrupt

    def run(self):
        """
        Top level routine for the entire life of the Job, using the job level timeout.
        Python only supports one alarm on SIGALRM - any Action without a connection
        will have a default timeout which will use SIGALRM. So the overarching Job timeout
        can only stop processing actions if the job wide timeout is exceeded.
        """
        return_code = 0
        error_msg = None
        try:
            # Set the signal handler
            signal.signal(signal.SIGINT, self.cancelling_handler)
            signal.signal(signal.SIGTERM, self.cancelling_handler)

            # Setup the protocols
            for protocol in self.protocols:
                try:
                    protocol.set_up()
                except (KeyError, TypeError) as exc:
                    self.logger.error("Unable to setup the protocols")
                    self.logger.exception(exc)
                    raise RuntimeError(exc)
                if not protocol.valid:
                    msg = "protocol %s has errors: %s" % (protocol.name, protocol.errors)
                    self.logger.exception(msg)
                    raise JobError(msg)

            # Run the pipeline and wait for exceptions
            with self.timeout() as max_end_time:
                self.pipeline.run_actions(self.connection, max_end_time)
        except LAVAError as exc:
            error_msg = exc.error_msg
            return_code = exc.error_code
        except RuntimeError:
            # TODO: should be replaced by LAVABug
            error_msg = "RuntimeError: this is probably a bug in LAVA, please report it."
            return_code = 3
        except KeyboardInterrupt:
            error_msg = "KeyboardInterrupt: the job was canceled."
            return_code = 6
        except Exception as exc:
            self.logger.exception(traceback.format_exc())
            error_msg = "%s: unknown exception, please report it" % exc.__class__.__name__
            return_code = 7

        # Cleanup now
        self.cleanup(self.connection)

        result_dict = {"definition": "lava",
                       "case": "job"}
        if error_msg:
            result_dict["result"] = "fail"
            self.logger.results(result_dict)
            self.logger.error(error_msg)
        elif self.pipeline.errors:
            result_dict["result"] = "fail"
            self.logger.results(result_dict)
            self.logger.error("Errors detected: %s", self.pipeline.errors)
            return_code = -1
        else:
            result_dict["result"] = "pass"
            self.logger.results(result_dict)
            self.logger.info("Job finished correctly")
        return return_code

    def cleanup(self, connection):
        if self.cleaned:
            self.logger.info("Cleanup already called, skipping")

        # exit out of the pipeline & run the Finalize action to close the
        # connection and poweroff the device (the cleanup action will do that
        # for us)
        self.logger.info("Cleaning after the job")
        self.pipeline.cleanup(connection)

        for tmp_dir in self.base_overrides.values():
            self.logger.info("Override tmp directory removed at %s", tmp_dir)
            try:
                shutil.rmtree(tmp_dir)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.error("Unable to remove the directory: %s",
                                      exc.strerror)

        if self.tmp_dir is not None:
            self.logger.info("Root tmp directory removed at %s", self.tmp_dir)
            try:
                shutil.rmtree(self.tmp_dir)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.error("Unable to remove the directory: %s",
                                      exc.strerror)

        # Mark cleanup as done to avoid calling it many times
        self.cleaned = True
