# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import datetime
import errno
import os
import shutil
import tempfile
import time
import traceback
from typing import TYPE_CHECKING

import pytz

from lava_common.constants import CLEANUP_TIMEOUT, DISPATCHER_DOWNLOAD_DIR
from lava_common.exceptions import JobError, LAVABug, LAVAError
from lava_common.version import __version__
from lava_dispatcher.logical import PipelineContext
from lava_dispatcher.protocols.multinode import (  # pylint: disable=unused-import
    MultinodeProtocol,
)

if TYPE_CHECKING:
    from logging import Logger
    from typing import Any

    from lava_common.timeout import Timeout

    from .device import Device


class Job:
    """
    Populated by the parser, the Job contains all of the
    Actions and their pipelines.
    parameters provides the immutable data about this job:
        action_timeout
        job_name
        priority
        device_type (mapped to target by scheduler)
        logging_level
        job_timeout
    Job also provides the primary access to the Device.
    The NewDevice class only loads the specific configuration of the
    device for this job - one job, one device.
    """

    def __init__(
        self,
        job_id: int,
        parameters: dict[str, Any],
        logger: Logger,
        device: Device,
        timeout: Timeout,
    ):
        self.job_id = job_id
        self.logger = logger
        self.device = device
        self.parameters = parameters
        self.__context__ = PipelineContext()
        self.pipeline = None
        self.connection = None
        self.timeout = timeout
        self.protocols = []
        # Was the job cleaned
        self.cleaned = False
        # override in use
        self.base_overrides = {}
        self.started = False
        self.test_info = {}

    @property
    def context(self):
        return self.__context__.pipeline_data

    @context.setter
    def context(self, data):
        self.__context__.pipeline_data.update(data)

    def describe(self):
        return {
            "pipeline": self.pipeline.describe(),
        }

    @property
    def tmp_dir(self):
        return self.get_basedir(DISPATCHER_DOWNLOAD_DIR)

    def get_basedir(self, path):
        prefix = self.parameters.get("dispatcher", {}).get("prefix", "")
        return os.path.join(path, "%s%s" % (prefix, self.job_id))

    def mkdtemp(self, action_name, override=None):
        """
        Create a tmp directory in DISPATCHER_DOWNLOAD_DIR/{job_id}/ because
        this directory will be removed when the job finished, making cleanup
        easier.
        """
        if override is None:
            create_base_dir = True
            base_dir = self.tmp_dir
        else:
            if override in self.base_overrides:
                create_base_dir = False
                base_dir = self.base_overrides[override]
            else:
                create_base_dir = True
                base_dir = self.get_basedir(override)

        if create_base_dir:
            # Try to create the directory.
            os.makedirs(base_dir, mode=0o755, exist_ok=True)
            # Save the path for the next calls (only if that's not an override)
            if override:
                self.base_overrides[override] = base_dir

        # Create the sub-directory
        tmp_dir = tempfile.mkdtemp(prefix=action_name + "-", dir=base_dir)
        os.chmod(tmp_dir, 0o755)  # nosec - automatic cleanup.
        return tmp_dir

    def _validate(self):
        """
        Validate the pipeline and raise an exception (that inherit from
        LAVAError) if it fails.
        """
        self.logger.info(
            "Start time: %s (UTC)", pytz.utc.localize(datetime.datetime.utcnow())
        )
        for protocol in self.protocols:
            try:
                protocol.configure(self.device, self)
            except LAVAError:
                self.logger.error("Configuration failed for protocol %s", protocol.name)
                raise
            except Exception as exc:
                self.logger.error("Configuration failed for protocol %s", protocol.name)
                self.logger.exception(traceback.format_exc())
                raise LAVABug(exc)

            if not protocol.valid:
                msg = "protocol %s has errors: %s" % (protocol.name, protocol.errors)
                self.logger.exception(msg)
                raise JobError(msg)

        # Check that namespaces are used in all actions or none
        namespaces = set()
        for action in self.parameters["actions"]:
            action_name = list(action.keys())[0]
            namespaces.add(action[action_name]["namespace"])

        # 'common' is a reserved namespace that should not be present with
        # other namespaces.
        if len(namespaces) > 1 and "common" in namespaces:
            msg = "'common' is a reserved namespace that should not be present with other namespaces"
            self.logger.error(msg)
            self.logger.debug("Namespaces: %s", ", ".join(namespaces))
            raise JobError(msg)
        if "docker-test-shell" in namespaces:
            msg = "'docker-test-shell' is a reserved namespace and can't be used in job definitions"
            self.logger.error(msg)
            self.logger.debug("Namespaces: %s", ", ".join(namespaces))
            raise JobError(msg)

        # validate the pipeline
        self.pipeline.validate_actions()

    def validate(self):
        """
        Public wrapper for the pipeline validation.
        Send a "fail" results if needed.
        """
        label = "lava-dispatcher, installed at version: %s" % __version__
        self.logger.info(label)
        self.logger.info("start: 0 validate")
        start = time.monotonic()

        success = False
        try:
            with self.timeout(None, None) as max_end_time:
                self._validate()
                success = True
        except LAVAError:
            raise
        except Exception as exc:
            # provide useful info on command line, e.g. failed unit tests.
            self.logger.exception(traceback.format_exc())
            raise LAVABug(exc)
        finally:
            self.logger.info("validate duration: %.02f", time.monotonic() - start)
            self.logger.results(
                {
                    "definition": "lava",
                    "case": "validate",
                    "result": "pass" if success else "fail",
                }
            )
            if not success:
                self.cleanup(connection=None)

    def _run(self):
        """
        Run the pipeline under the run() wrapper that will catch the exceptions
        """
        self.started = True

        # Setup the protocols
        for protocol in self.protocols:
            try:
                protocol.set_up()
            except LAVAError:
                raise
            except Exception as exc:
                self.logger.error("Unable to setup the protocols")
                self.logger.exception(traceback.format_exc())
                raise LAVABug(exc)

            if not protocol.valid:
                msg = "protocol %s has errors: %s" % (protocol.name, protocol.errors)
                self.logger.exception(msg)
                raise JobError(msg)

        # Run the pipeline and wait for exceptions
        with self.timeout(None, None) as max_end_time:
            self.pipeline.run_actions(self.connection, max_end_time)

    def run(self):
        """
        Top level routine for the entire life of the Job, using the job level timeout.
        Python only supports one alarm on SIGALRM - any Action without a connection
        will have a default timeout which will use SIGALRM. So the overarching Job timeout
        can only stop processing actions if the job wide timeout is exceeded.
        """
        try:
            self._run()
        finally:
            # Cleanup now
            self.cleanup(self.connection)

    def cleanup(self, connection):
        self.timeout.name = "job-cleanup"
        with self.timeout(None, time.monotonic() + CLEANUP_TIMEOUT) as max_end_time:
            return self._cleanup(connection, max_end_time)

    def _cleanup(self, connection, max_end_time):
        if self.cleaned:
            self.logger.info("Cleanup already called, skipping")
            return

        # exit out of the pipeline & run the Finalize action to close the
        # connection and poweroff the device (the cleanup action will do that
        # for us)
        self.logger.info("Cleaning after the job")
        self.pipeline.cleanup(connection, max_end_time)

        for tmp_dir in self.base_overrides.values():
            self.logger.info("Removing override tmp directory at %s", tmp_dir)
            try:
                shutil.rmtree(tmp_dir)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.error(
                        "Unable to remove the directory: %s", exc.strerror
                    )

        if self.tmp_dir is not None:
            self.logger.info("Removing root tmp directory at %s", self.tmp_dir)
            try:
                shutil.rmtree(self.tmp_dir)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    self.logger.error(
                        "Unable to remove the directory: %s", exc.strerror
                    )

        # Mark cleanup as done to avoid calling it many times
        self.cleaned = True
