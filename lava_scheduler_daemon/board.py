import json
import os
import signal
import sys
import tempfile
import logging

from twisted.internet.error import ProcessDone, ProcessExitedAlready
from twisted.internet.protocol import ProcessProtocol
from twisted.internet import defer, task
from twisted.protocols.basic import LineReceiver


def catchall_errback(logger):
    def eb(failure):
        logger.error(
            '%s: %s\n%s', failure.type.__name__, failure.value,
            failure.getTraceback())
    return eb

OOB_FD = 3


class OOBDataProtocol(LineReceiver):

    delimiter = '\n'

    def __init__(self, source, board_name, _source_lock):
        self.logger = logging.getLogger(__name__ + '.OOBDataProtocol')
        self.source = source
        self.board_name = board_name
        self._source_lock = _source_lock

    def lineReceived(self, line):
        if ':' not in line:
            self.logger.error('malformed oob data: %r' % line)
            return
        key, value = line.split(':', 1)
        self._source_lock.run(
            self.source.jobOobData, self.board_name, key,
            value.lstrip()).addErrback(
                catchall_errback(self.logger))


class DispatcherProcessProtocol(ProcessProtocol):


    def __init__(self, deferred, log_file, job):
        self.logger = logging.getLogger(__name__ + '.DispatcherProcessProtocol')
        self.deferred = deferred
        self.log_file = log_file
        self.log_size = 0
        self.job = job
        self.oob_data = OOBDataProtocol(
            job.source, job.board_name, job._source_lock)

    def childDataReceived(self, childFD, data):
        if childFD == OOB_FD:
            self.oob_data.dataReceived(data)
        self.log_file.write(data)
        self.log_size += len(data)
        if self.log_size > self.job.daemon_options['LOG_FILE_SIZE_LIMIT']:
            if not self.job._killing:
                self.job.cancel("exceeded log size limit")
        self.log_file.flush()

    def processExited(self, reason):
        self.logger.info("processExited for %s: %s",
            self.job.board_name, reason.value)

    def processEnded(self, reason):
        self.logger.info("processEnded for %s: %s",
            self.job.board_name, reason.value)
        self.log_file.close()
        self.deferred.callback(reason.value.exitCode)


class Job(object):


    def __init__(self, job_data, dispatcher, source, board_name, reactor,
                 daemon_options, log_to_stdout=False):
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
        self.job_log_file = None
        self._log_to_stdout = log_to_stdout

    def _checkCancel(self):
        if self._killing:
            self.cancel()
        else:
            return self._source_lock.run(
                self.source.jobCheckForCancellation, self.board_name).addCallback(
                self._maybeCancel)

    def cancel(self, reason=None):
        if not self._killing and reason is None:
            reason = "killing job for unknown reason"
        if not self._killing:
            self.logger.info(reason)
            self.job_log_file.write("\n%s\n" % reason.upper())
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
        if self._log_to_stdout:
            return self._run(sys.stdout)

        d = self.source.getLogFileForJobOnBoard(self.board_name)
        return d.addCallback(self._run).addErrback(
            catchall_errback(self.logger))

    def _run(self, job_log_file):
        d = defer.Deferred()
        json_data = self.job_data
        fd, self._json_file = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            json.dump(json_data, f)
        self._protocol = DispatcherProcessProtocol(
            d, job_log_file, self)
        self.job_log_file = job_log_file
        self.reactor.spawnProcess(
            self._protocol, self.dispatcher, args=[
                self.dispatcher, self._json_file, '--oob-fd', str(OOB_FD)],
            childFDs={0:0, 1:'r', 2:'r', OOB_FD:'r'}, env=None)
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
        self.logger.info("reporting job completed")
        if self._time_limit_call is not None:
            self._time_limit_call.cancel()
        self._checkCancel_call.stop()
        return self._source_lock.run(
            self.source.jobCompleted, self.board_name, exit_code).addCallback(
            lambda r:exit_code)


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
                 daemon_options, use_celery=False):
        self.logger = logging.getLogger(__name__ + '.MonitorJob')
        self.job_data = job_data
        self.dispatcher = dispatcher
        self.source = source
        self.board_name = board_name
        self.reactor = reactor
        self.daemon_options = daemon_options
        self.use_celery = use_celery
        self._json_file = None

    def run(self):
        d = defer.Deferred()
        json_data = self.job_data
        fd, self._json_file = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            json.dump(json_data, f)

        childFDs = {0:0, 1:1, 2:2}
        if self.use_celery:
            args = [
                'setsid', 'lava', 'celery-schedulermonitor',
                self.dispatcher, str(self.board_name), self._json_file]
        else:
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


class Board(object):
    """
    A board runs jobs.  A board can be in four main states:

     * stopped (S)
       * the board is not looking for or processing jobs
     * checking (C)
       * a call to check for a new job is in progress
     * waiting (W)
       * no job was found by the last call to getJobForBoard and so the board
         is waiting for a while before calling again.
     * running (R)
       * a job is running (or a job has completed but the call to jobCompleted
         on the job source has not)

    In addition, because we can't stop a job instantly nor abort a check for a
    new job safely (because a if getJobForBoard returns a job, it has already
    been marked as started), there are variations on the 'checking' and
    'running' states -- 'checking with stop requested' (C+S) and 'running with
    stop requested' (R+S).  Even this is a little simplistic as there is the
    possibility of .start() being called before the process of stopping
    completes, but we deal with this by deferring any actions taken by
    .start() until the board is really stopped.

    Events that cause state transitions are:

     * start() is called.  We cheat and pretend that this can only happen in
       the stopped state by stopping first, and then move into the C state.

     * stop() is called.  If we in the C or R state we move to C+S or R+S
       resepectively.  If we are in S, C+S or R+S, we stay there.  If we are
       in W, we just move straight to S.

     * getJobForBoard() returns a job.  We can only be in C or C+S here, and
       move into R or R+S respectively.

     * getJobForBoard() indicates that there is no job to perform.  Again we
       can only be in C or C+S and move into W or S respectively.

     * a job completes (i.e. the call to jobCompleted() on the source
       returns).  We can only be in R or R+S and move to C or S respectively.

     * the timer that being in state W implies expires.  We move into C.

    The cheating around start means that interleaving start and stop calls may
    not always do what you expect.  So don't mess around in that way please.
    """

    job_cls = MonitorJob

    def __init__(self, source, board_name, dispatcher, reactor, daemon_options,
                use_celery=False, job_cls=None):
        self.source = source
        self.board_name = board_name
        self.dispatcher = dispatcher
        self.reactor = reactor
        self.daemon_options = daemon_options
        if job_cls is not None:
            self.job_cls = job_cls
        self.running_job = None
        self._check_call = None
        self._stopping_deferreds = []
        self.logger = logging.getLogger(__name__ + '.Board.' + board_name)
        self.checking = False
        self.use_celery = use_celery

    def _state_name(self):
        if self.running_job:
            state = "R"
        elif self._check_call:
            assert not self._stopping_deferreds
            state = "W"
        elif self.checking:
            state = "C"
        else:
            assert not self._stopping_deferreds
            state = "S"
        if self._stopping_deferreds:
            state += "+S"
        return state

    def start(self):
        self.logger.debug("start requested")
        self.stop().addCallback(self._start)

    def _start(self, ignored):
        self.logger.debug("starting")
        self._stopping_deferreds = []
        self._checkForJob()

    def stop(self):
        self.logger.debug("stopping")
        if self._check_call is not None:
            self._check_call.cancel()
            self._check_call = None

        if self.running_job is not None or self.checking:
            self.logger.debug("job running; deferring stop")
            self._stopping_deferreds.append(defer.Deferred())
            return self._stopping_deferreds[-1]
        else:
            self.logger.debug("stopping immediately")
            return defer.succeed(None)

    def _checkForJob(self):
        self.logger.debug("checking for job")
        self._check_call = None
        self.checking = True
        self.source.getJobForBoard(self.board_name).addCallbacks(
            self._maybeStartJob, self._ebCheckForJob)

    def _ebCheckForJob(self, result):
        self.logger.error(
            '%s: %s\n%s', result.type.__name__, result.value,
            result.getTraceback())
        self._maybeStartJob(None)

    def _finish_stop(self):
        self.logger.debug(
            "calling %s deferreds returned from stop()",
            len(self._stopping_deferreds))
        for d in self._stopping_deferreds:
            d.callback(None)
        self._stopping_deferreds = []

    def _maybeStartJob(self, job_data):
        self.checking = False
        if job_data is None:
            self.logger.debug("no job found")
            if self._stopping_deferreds:
                self._finish_stop()
            else:
                self._check_call = self.reactor.callLater(
                    10, self._checkForJob)
            return
        self.logger.info("starting job %r", job_data)
        self.running_job = self.job_cls(
            job_data, self.dispatcher, self.source, self.board_name,
            self.reactor, self.daemon_options, self.use_celery)
        d = self.running_job.run()
        d.addCallbacks(self._cbJobFinished, self._ebJobFinished)

    def _ebJobFinished(self, result):
        self.logger.exception(result.value)
        self._checkForJob()

    def _cbJobFinished(self, result):
        self.running_job = None
        if self._stopping_deferreds:
            self._finish_stop()
        else:
            self._checkForJob()
