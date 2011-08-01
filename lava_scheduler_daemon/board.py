import json
import os
import tempfile
import logging

from twisted.internet.protocol import ProcessProtocol
from twisted.internet import defer



class DispatcherProcessProtocol(ProcessProtocol):

    logger = logging.getLogger(__name__ + '.DispatcherProcessProtocol')

    def __init__(self, deferred, log_file):
        print log_file
        self.deferred = deferred
        self.log_file = log_file

    def outReceived(self, text):
        self.log_file.write(text)
        self.log_file.flush()

    errReceived = outReceived

    def processEnded(self, reason):
        # This discards the process exit value.
        self.log_file.close()
        self.deferred.callback(None)


class Job(object):

    logger = logging.getLogger(__name__ + '.Job')

    def __init__(self, job_data, dispatcher, reactor):
        self.job_data = job_data
        self.dispatcher = dispatcher
        self.reactor = reactor
        self._json_file = None

    def run(self):
        d = defer.Deferred()
        json_data, log_file = self.job_data
        fd, self._json_file = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            json.dump(json_data, f)
        self.reactor.spawnProcess(
            DispatcherProcessProtocol(d, log_file), self.dispatcher,
            args=[self.dispatcher, self._json_file],
            childFDs={0:0, 1:'r', 2:'r'}, env=None)
        d.addBoth(self._exited)
        return d

    def _exited(self, result):
        self.logger.info("job finished on %s", self.job_data[0]['target'])
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

    job_cls = Job

    def __init__(self, source, board_name, dispatcher, reactor, job_cls=None):
        self.source = source
        self.board_name = board_name
        self.dispatcher = dispatcher
        self.reactor = reactor
        if job_cls is not None:
            self.job_cls = job_cls
        self.running_job = None
        self._check_call = None
        self._stopping_deferreds = []
        self.logger = logging.getLogger(__name__ + '.Board.' + board_name)
        self.checking = False

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
        self.logger.exception(result.value)
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
            job_data, self.dispatcher, self.reactor)
        d = self.running_job.run()
        d.addCallbacks(self._cbJobFinished, self._ebJobFinished)

    def _cbJobFinished(self, result):
        self.logger.info("reporting job completed")
        self.source.jobCompleted(
            self.board_name).addCallback(self._cbJobCompleted)

    def _ebJobFinished(self, result):
        self.logger.exception(result.value)
        self._checkForJob()

    def _cbJobCompleted(self, result):
        self.running_job = None
        if self._stopping_deferreds:
            self._finish_stop()
        else:
            self._checkForJob()
