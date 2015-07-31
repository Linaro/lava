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
import sys
import signal
import tempfile
import logging

from twisted.internet.error import ProcessDone, ProcessExitedAlready
from twisted.internet.protocol import ProcessProtocol
from twisted.internet import defer, task

# pylint: disable=invalid-name,too-many-instance-attributes,too-many-arguments,too-few-public-methods


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
        if childFD == 2:
            debug_path = os.path.join(self.job.output_dir, 'output.txt')
            # only add output if there is nothing else as later failures will be logged.
            if os.path.exists(debug_path) and os.stat(debug_path).st_size == 0:
                with open(debug_path, 'a') as logfile:
                    logfile.write("ERROR: %s\n" % data)
                self.logger.error("ERROR: %s", data)
                self.job.cancel(data)
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


# Common check function, adapted from /usr/lib/python2.7/dist-packages/twisted/internet/base.py:880:
# python-twisted-core 14.0.2-3 (codehelp)
def argChecker(arg):
    """
    Return either a str or None.  If the given value is not
    allowable for some reason, None is returned.  Otherwise, a
    possibly different object which should be used in place of arg
    is returned.  This forces unicode encoding to happen now, rather
    than implicitly later.

    This adapted version always returns something and that something
    will always pass the original argChecker in twisted, whilst logging
    warnings if changes had to be made.
    """
    logger = logging.getLogger('argChecker')
    defaultEncoding = sys.getdefaultencoding()
    if isinstance(arg, unicode):
        try:
            arg = arg.encode(defaultEncoding)
        except UnicodeEncodeError:
            logger.warning("arg failed to encode from unicode: %s", type(arg))
            arg = arg.encode('ascii', 'ignore')
            logger.warning("converted by dropping invalid characters: %s", arg)
            return arg
    if isinstance(arg, str) and '\0' not in arg:
        return arg
    elif arg is None:
        logger.warning("No argument passed")
        return ''
    else:
        arg = arg.replace('\0', '')
        logger.warning("%s contained null", arg)
        return arg


class Job(object):

    def __init__(self, job_id, job_data, dispatcher, source, board_name,
                 reactor, daemon_options):
        self.job_id = job_id
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
        self.output_dir = None

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
        self.logger.info('attempting to kill job with signal %s', signame)
        try:
            self._protocol.transport.signalProcess(getattr(signal, signame))
            self.logger.info('killed job with signal %s', signame)
        except ProcessExitedAlready:
            pass

    def _maybeCancel(self, cancel):
        if cancel:
            self.cancel("killing job by user request")
        else:
            self.logger.debug('running job id %s', self.job_id)

    def _time_limit_exceeded(self):
        self._time_limit_call = None
        self.cancel("killing job for exceeding timeout")

    def run(self):
        d = self.source.getOutputDirForJobOnBoard(self.board_name)
        if d:
            return d.addCallback(self._run).addErrback(
                catchall_errback(self.logger))
        return None

    def _run(self, output_dir):
        d = defer.Deferred()
        try:
            if not output_dir:
                raise ValueError("Missing output directory")
            json_data = self.job_data
            custom_config = json_data.pop('config', None)
            fd, self._json_file = tempfile.mkstemp()
            with os.fdopen(fd, 'wb') as f:
                json.dump(json_data, f)
            self.output_dir = output_dir
            args = [
                argChecker(self.dispatcher),
                argChecker(self._json_file),
                argChecker('--output-dir'),
                argChecker(output_dir)
            ]

            if custom_config:
                fd, self._device_config = tempfile.mkstemp()
                with os.fdopen(fd, 'wb') as f:
                    for k in custom_config:
                        f.write(k + '=' + custom_config[k] + "\n")
                args.append(argChecker('--config'))
                args.append(argChecker(self._device_config))

            # childFDs are given defaults ie., {0: 'w', 1:'r', 2:'r'}
            # See https://twistedmatrix.com/documents/14.0.1/core/howto/process.html#running-another-process for details.
            self._protocol = DispatcherProcessProtocol(d, self)

            self.logger.info('executing "%s"', ' '.join(args))

            ret = self.reactor.spawnProcess(self._protocol, self.dispatcher,
                                            args=args, env=None)
            if ret:
                self.logger.debug("reactor spawned process with status: %s", ret.status)
                if not os.path.exists(output_dir):
                    os.mkdir(output_dir)
                self._pidrecord = os.path.join(output_dir, "jobpid")
                with open(self._pidrecord, 'w') as f:
                    f.write("%s\n" % os.getpgid(ret.pid))
            self._checkCancel_call.start(10)
            timeout = max(
                json_data['timeout'], self.daemon_options['MIN_JOB_TIMEOUT'])
            self._time_limit_call = self.reactor.callLater(
                timeout, self._time_limit_exceeded)
        except (ValueError, TypeError) as exc:
            self.cancel(exc)
        d.addBoth(self._exited)
        return d

    def _exited(self, exit_code):
        self.logger.info("job finished on %s", self.job_data['target'])
        if self._json_file is not None:
            os.unlink(self._json_file)
        if self._pidrecord is not None and os.path.exists(self._pidrecord):
            os.unlink(self._pidrecord)
        if exit_code:
            self.logger.info("job incomplete: reported %s exit code", exit_code)
        else:
            self.logger.info("job complete")
        if self._time_limit_call is not None:
            self._time_limit_call.cancel()
        try:
            self._checkCancel_call.stop()
        except AssertionError:
            self.logger.exception("Job did not start")
        return self._source_lock.run(
            self.source.jobCompleted,
            self.job_id,
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

    def __init__(self, job, job_data, dispatcher, source, board_name, reactor,
                 daemon_options):
        self.logger = logging.getLogger(__name__ + '.MonitorJob')
        self.job = job
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

        # See https://twistedmatrix.com/documents/14.0.1/core/howto/process.html#running-another-process for details.
        childFDs = {0: 'w', 1: 'r', 2: 'r'}
        args = [
            'setsid', 'lava-server', 'manage', 'schedulermonitor',
            str(self.job.id), self.dispatcher, str(self.board_name),
            self._json_file, '-l', self.daemon_options['LOG_LEVEL']]
        if self.daemon_options['LOG_FILE_PATH']:
            args.extend(['-f', self.daemon_options['LOG_FILE_PATH']])
            childFDs = None
        self.logger.info('monitoring "%s"', ' '.join(args))
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

    def _prepareJob(self, status):  # pylint: disable=unused-argument
        self.source.getJobDetails(self.job).addCallbacks(
            self._startJob, self._ebStartJob)

    def _startJob(self, job_data):
        if job_data is None:
            self.logger.debug("no job found")
            return
        self.logger.info("starting job %r", job_data)

        self.running_job = self.job_cls(
            self.job, job_data, self.dispatcher, self.source, self.board_name,
            self.reactor, self.daemon_options)
        d = self.running_job.run()
        if d:
            d.addCallbacks(self._cbJobFinished, self._ebJobFinished)
        else:
            self.logger.info("Job failed to start")

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

    def _cbJobFinished(self, result):  # pylint: disable=unused-argument
        self.running_job = None
