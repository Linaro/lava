# Copyright (C) 2013 Linaro Limited
#
# Author: Senthil Kumaran <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Scheduler.
#
# LAVA Scheduler is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3 as
# published by the Free Software Foundation
#
# LAVA Scheduler is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Scheduler.  If not, see <http://www.gnu.org/licenses/>.

import logging

from twisted.internet import defer
from lava_scheduler_daemon.board import MonitorJob, catchall_errback

class NewJob(object):
    job_cls = MonitorJob

    def __init__(self, source, job, dispatcher, reactor, daemon_options,
                 job_cls=None):
        self.source = source
        self.dispatcher = dispatcher
        self.reactor = reactor
        self.daemon_options = daemon_options
        self.job = job
        if job.actual_device:
            self.board_name = job.actual_device.hostname
        elif job.requested_device:
            self.board_name = job.requested_device.hostname
        if job_cls is not None:
            self.job_cls = job_cls
        self.running_job = None
        self.logger = logging.getLogger(__name__ + '.NewJob.' + str(job.id))

    def start(self):
        self.logger.debug("processing job")
        if self.job is None:
            self.logger.debug("no job found for processing")
            return
        self.source.getJobDetails(self.job).addCallbacks(
            self._startJob, self._ebStartJob)

    def _startJob(self, job_data):
        if job_data is None:
            self.logger.debug("no job found")
            return
        self.logger.info("starting job %r", job_data)
        
        self.running_job = self.job_cls(
            job_data, self.dispatcher, self.source, self.board_name,
            self.reactor, self.daemon_options)
        d = self.running_job.run()
        d.addCallbacks(self._cbJobFinished, self._ebJobFinished)

    def _ebStartJob(self, result):
        self.logger.error(
            '%s: %s\n%s', result.type.__name__, result.value,
            result.getTraceback())
        return

    def stop(self):
        self.logger.debug("stopping")

        if self.running_job is not None:
            self.logger.debug("job running; deferring stop")
        else:
            self.logger.debug("stopping immediately")
            return defer.succeed(None)

    def _ebJobFinished(self, result):
        self.logger.exception(result.value)

    def _cbJobFinished(self, result):
        self.running_job = None
