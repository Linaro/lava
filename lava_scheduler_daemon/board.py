import json
import os
import tempfile
import logging

from twisted.internet.protocol import ProcessProtocol
from twisted.internet import defer


logger = logging.getLogger(__name__)


class DispatcherProcessProtocol(ProcessProtocol):

    logger = logger.getChild('DispatcherProcessProtocol')

    def __init__(self, deferred):
        self.deferred = deferred

    def connectionMade(self):
        fd, self._logpath = tempfile.mkstemp()
        self._output = os.fdopen(fd, 'wb')

    def outReceived(self, text):
        self._output.write(text)

    errReceived = outReceived

    def processEnded(self, reason):
        # This discards the process exit value.
        self._output.close()
        self.deferred.callback(self._logpath)


class Job(object):

    logger = logger.getChild('Job')

    def __init__(self, json_data, dispatcher, reactor):
        self.json_data = json_data
        self.dispatcher = dispatcher
        self.reactor = reactor
        self._json_file = None

    def run(self):
        d = defer.Deferred()
        fd, self._json_file = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            json.dump(self.json_data, f)
        self.reactor.spawnProcess(
            DispatcherProcessProtocol(d), self.dispatcher,
            args=[self.dispatcher, self._json_file],
            childFDs={0:0, 1:'r', 2:'r'})
        d.addBoth(self._exited)
        return d

    def _exited(self, log_file_path):
        self.logger.info("job finished on %s", self.json_data['target'])
        if self._json_file is not None:
            os.unlink(self._json_file)
        return log_file_path


class Board(object):

    logger = logger.getChild('Board')

    def __init__(self, source, board_name, dispatcher, reactor):
        self.source = source
        self.board_name = board_name
        self.dispatcher = dispatcher
        self.reactor = reactor
        self.running_job = None
        self._check_call = None
        self._stopping_deferred = []
        self.logger = self.logger.getChild(board_name)

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

        if self.running_job is not None:
            self.logger.debug("job running; deferring stop")
            self._stopping_deferreds.append(defer.Deferred())
            return self._stopping_deferreds[-1]
        else:
            self.logger.debug("stopping immediately")
            return defer.succeed(None)

    def _checkForJob(self):
        self.logger.debug("checking for job")
        self._check_call = None
        self.source.getJobForBoard(self.board_name).addCallback(
            self._maybeStartJob)

    def _maybeStartJob(self, json_data):
        if json_data is None:
            self.logger.debug("no job found")
            self._check_call = self.reactor.callLater(10, self._checkForJob)
            return
        self.logger.debug("starting job")
        self.running_job = Job(json_data, self.dispatcher, self.reactor)
        d = self.running_job.run()
        d.addCallback(self.jobCompleted)


    def jobCompleted(self, log_file_path):
        self.logger.info("reporting job completed")
        self.running_job = None
        self.source.jobCompleted(
            self.board_name, open(log_file_path, 'rb')). addCallback(
            self._cbJobCompleted)

    def _cbJobCompleted(self, result):
        if self._stopping_deferreds:
            self.logger.debug(
                "calling %s deferreds returned from stop()",
                len(self._stopping_deferreds))
            for d in self._stopping_deferreds:
                d.callback(None)
        else:
            self._checkForJob()
