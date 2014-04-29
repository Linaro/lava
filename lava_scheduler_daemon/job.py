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

import json
import os
import signal
import tempfile
import logging

from twisted.internet.error import ProcessDone, ProcessExitedAlready
from twisted.internet.protocol import ProcessProtocol
from twisted.internet import defer, task


def catchall_errback(logger):
    def eb(failure):
        logger.error(
            '%s: %s\n%s', failure.type.__name__, failure.value,
            failure.getTraceback())
    return eb


class DispatcherProcessProtocol(ProcessProtocol):

    def __init__(self, deferred, job):
        self.logger = logging.getLogger(__name__ + '.DispatcherProcessProtocol')
        self.deferred = deferred
        self.log_size = 0
        self.job = job

    def childDataReceived(self, childFD, data):
        self.log_size += len(data)
        if self.log_size > self.job.daemon_options['LOG_FILE_SIZE_LIMIT']:
            if not self.job._killing:
                self.job.cancel("exceeded log size limit")

    def childConnectionLost(self, childFD):
        self.logger.info("childConnectionLost for %s: %s",
                         self.job.board_name, childFD)

    def processExited(self, reason):
        self.logger.info("processExited for %s: %s",
                         self.job.board_name, reason.value)

    def processEnded(self, reason):
        self.logger.info("processEnded for %s: %s",
                         self.job.board_name, reason.value)
        self.deferred.callback(reason.value.exitCode)


class Job(object):

    def __init__(self, job_data, dispatcher, source, board_name, reactor,
                 daemon_options):
        self.job_data = job_data
        self.dispatcher = dispatcher
        self.source = source
        self.board_name = board_name
        self.logger = logging.getLogger(__name__ + '.Job.' + board_name)
        self.reactor = reactor
        self.daemon_options = daemon_options
        self._json_file = None
        self._source_lock = defer.DeferredLock()
        self._checkCancel_call = task.LoopingCall(self._checkCancel)
        self._signals = ['SIGINT', 'SIGINT', 'SIGTERM', 'SIGTERM', 'SIGKILL']
        self._time_limit_call = None
        self._killing = False
        self._kill_reason = ''
        self._pidrecord = None
        self._device_config = None

    def _checkCancel(self):
        if self._killing:
            self.cancel()
        else:
            return self._source_lock.run(
                self.source.jobCheckForCancellation,
                self.board_name).addCallback(self._maybeCancel)

    def cancel(self, reason=None):
        if not self._killing:
            if reason is None:
                reason = "killing job for unknown reason"
            self._kill_reason = reason
            self.logger.info(reason)
        self._killing = True
        if self._signals:
            signame = self._signals.pop(0)
        else:
            self.logger.warning("self._signals is empty!")
            signame = 'SIGKILL'
        self.logger.info(
            'attempting to kill job with signal %s' % signame)
        try:
            self._protocol.transport.signalProcess(getattr(signal, signame))
        except ProcessExitedAlready:
            pass

    def _maybeCancel(self, cancel):
        if cancel:
            self.cancel("killing job by user request")
        else:
            logging.debug('not cancelling')

    def _time_limit_exceeded(self):
        self._time_limit_call = None
        self.cancel("killing job for exceeding timeout")

    def run(self):
        d = self.source.getOutputDirForJobOnBoard(self.board_name)
        return d.addCallback(self._run).addErrback(
            catchall_errback(self.logger))

    def _run(self, output_dir):
        d = defer.Deferred()
        json_data = self.job_data
        custom_config = json_data.pop('config', None)
        fd, self._json_file = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            json.dump(json_data, f)

        args = [self.dispatcher, self._json_file, '--output-dir', output_dir]

        if custom_config:
            fd, self._device_config = tempfile.mkstemp()
            with os.fdopen(fd, 'wb') as f:
                for k in custom_config:
                    f.write(k + '=' + custom_config[k] + "\n")
            args.append('--config')
            args.append(self._device_config)

        self._protocol = DispatcherProcessProtocol(d, self)
        ret = self.reactor.spawnProcess(self._protocol, self.dispatcher,
                                        args=args, env=None,
                                        childFDs={0: 0, 1: 'r', 2: 'r'})
        if ret:
            os.mkdir(output_dir)
            self._pidrecord = os.path.join(output_dir, "jobpid")
            with open(self._pidrecord, 'w') as f:
                f.write("%s\n" % os.getpgid(ret.pid))
        self._checkCancel_call.start(10)
        timeout = max(
            json_data['timeout'], self.daemon_options['MIN_JOB_TIMEOUT'])
        self._time_limit_call = self.reactor.callLater(
            timeout, self._time_limit_exceeded)
        d.addBoth(self._exited)
        return d

    def _exited(self, exit_code):
        self.logger.info("job finished on %s", self.job_data['target'])
        if self._json_file is not None:
            os.unlink(self._json_file)
        if self._pidrecord is not None and os.path.exists(self._pidrecord):
            os.unlink(self._pidrecord)
        self.logger.info("reporting job completed")
        if self._time_limit_call is not None:
            self._time_limit_call.cancel()
        self._checkCancel_call.stop()
        return self._source_lock.run(
            self.source.jobCompleted,
            self.board_name,
            exit_code,
            self._killing).addCallback(lambda r: exit_code)


class SchedulerMonitorPP(ProcessProtocol):

    def __init__(self, d, board_name):
        self.d = d
        self.board_name = board_name
        self.logger = logging.getLogger(__name__ + '.SchedulerMonitorPP')

    def childDataReceived(self, childFD, data):
        self.logger.warning(
            "scheduler monitor for %s produced output: %r on fd %s",
            self.board_name, data, childFD)

    def processEnded(self, reason):
        if not reason.check(ProcessDone):
            self.logger.error(
                "scheduler monitor for %s crashed: %s",
                self.board_name, reason)
        self.d.callback(None)


class MonitorJob(object):

    def __init__(self, job_data, dispatcher, source, board_name, reactor,
                 daemon_options):
        self.logger = logging.getLogger(__name__ + '.MonitorJob')
        self.job_data = job_data
        self.dispatcher = dispatcher
        self.source = source
        self.board_name = board_name
        self.reactor = reactor
        self.daemon_options = daemon_options
        self._json_file = None

    def run(self):
        d = defer.Deferred()
        json_data = self.job_data
        fd, self._json_file = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            json.dump(json_data, f)

        childFDs = {0: 0, 1: 1, 2: 2}
        args = [
            'setsid', 'lava-server', 'manage', 'schedulermonitor',
            self.dispatcher, str(self.board_name), self._json_file,
            '-l', self.daemon_options['LOG_LEVEL']]
        if self.daemon_options['LOG_FILE_PATH']:
            args.extend(['-f', self.daemon_options['LOG_FILE_PATH']])
            childFDs = None
        self.logger.info('executing "%s"', ' '.join(args))
        self.reactor.spawnProcess(
            SchedulerMonitorPP(d, self.board_name), 'setsid',
            childFDs=childFDs, env=None, args=args)
        d.addBoth(self._exited)
        return d

    def _exited(self, result):
        if self._json_file is not None:
            os.unlink(self._json_file)
        return result


class JobRunner(object):
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
        self.logger = logging.getLogger(__name__ + '.JobRunner.' + str(job.id))

    def start(self):
        self.logger.debug("processing job")
        if self.job is None:
            self.logger.debug("no job found for processing")
            return
        self.source.jobStarted(self.job).addCallback(self._prepareJob)

    def _prepareJob(self, status):
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
