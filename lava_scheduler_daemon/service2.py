import json
import logging
import os
import tempfile

from twisted.application.service import Service
from twisted.internet import defer
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.task import LoopingCall


class IJobSource(object):

    def getBoardList():
        pass

    def getJobForBoard(board_name):
        pass

    def jobCompleted(board_name, log_stream):
        pass


class DispatcherProcessProtocol(ProcessProtocol):

    logger = logging.getLogger('DispatcherProcessProtocol')

    def __init__(self, deferred):
        self.deferred = deferred

    def connectionMade(self):
        fd, self._logpath = tempfile.mkstemp()
        self._output = os.fdopen(fd, 'wb')

    def outReceived(self, text):
        print 'received', repr(text)
        self._output.write(text)

    errReceived = outReceived

    def processEnded(self, reason):
        # This discards the process exit value.
        self._output.close()
        self.deferred.callback(self._logpath)


class Job(object):

    logger = logging.getLogger('Job')

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

    logger = logging.getLogger('Board')

    def __init__(self, source, board_name, dispatcher, reactor):
        self.source = source
        self.board_name = board_name
        self.dispatcher = dispatcher
        self.reactor = reactor
        self.running_job = None
        self._check_call = None
        self._stopping_deferred = []

    def start(self):
        self.stop().addCallback(self._start)

    def _start(self, ignored):
        self._stopping_deferreds = []
        self._checkForJob()

    def stop(self):
        if self._check_call is not None:
            self._check_call.cancel()
            self._check_call = None

        if self.running_job is not None:
            self._stopping_deferreds.append(defer.Deferred())
            return self._stopping_deferreds[-1]
        else:
            return defer.succeed(None)

    def _checkForJob_ignore_arg(self, result):
        self._checkForJob()

    def _checkForJob(self):
        self._check_call = None
        self.source.getJobForBoard(self.board_name).addCallback(
            self._maybeStartJob)

    def _maybeStartJob(self, json_data):
        if json_data is None:
            self._check_call = self.reactor.callLater(10, self._checkForJob)
            return
        self.running_job = Job(json_data, self.dispatcher, self.reactor)
        d = self.running_job.run()
        d.addCallback(self.jobCompleted)

    def jobCompleted(self, log_file_path):
        self.logger.info(
            "reporting job finished on %s", self.running_job.json_data['target'])
        self.running_job = None
        def _cb(result):
            if self._stopping_deferreds:
                for d in self._stopping_deferreds:
                    d.callback(None)
            else:
                self._checkForJob()
        self.source.jobCompleted(self.board_name, open(log_file_path, 'rb'))


class BoardSet(Service):

    logger = logging.getLogger('BoardSet')

    def __init__(self, source, dispatcher, reactor):
        self.source = source
        self.boards = {}
        self.dispatcher = dispatcher
        self.reactor = reactor
        self._update_boards_call = LoopingCall(self.updateBoards)
        self._update_boards_call.clock = reactor

    def updateBoards(self):
        self.logger.info("Refreshing board list")
        return self.source.getBoardList().addCallback(self._cbUpdateBoards)

    def _cbUpdateBoards(self, board_names):
        self.logger.info("New board list %s", board_names)
        new_boards = {}
        for board_name in board_names:
            if board_name in self.boards:
                new_boards[board_name] = self.boards.pop(board_name)
            else:
                new_boards[board_name] = Board(
                    self.source, board_name, self.dispatcher, self.reactor)
                new_boards[board_name].start()
        for board in self.boards.values():
            board.stop()
        self.boards = new_boards

    def startService(self):
        self._update_boards_call.start(20)

    def stopService(self):
        self._update_boards_call.stop()
        ds = []
        for board in self.boards.itervalues():
            ds.append(board.stop())
        return defer.gatherResults(ds)


class DirectoryJobSource(object):

    logger = logging.getLogger('DirectoryJobSource')

    def __init__(self, directory):
        self.directory = directory
        if not self.directory.isdir():
            self.logger.critical("%s is not a directory", self.directory)
            raise RuntimeError("%s must be a directory" % self.directory)
        boards = self.directory.child('boards')
        if not boards.isdir():
            self.logger.critical("%s is not a directory", boards)
            raise RuntimeError("%s must be a directory" % boards)
        for subdir in 'incoming', 'running', 'completed', 'broken':
            subdir = self.directory.child(subdir)
            if not subdir.isdir():
                subdir.createDirectory()
        self.logger.info("starting to look for jobs in %s", self.directory)

    def _getBoardList(self):
        return self.directory.child('boards').listdir()

    def getBoardList(self):
        return defer.maybeDeferred(self._getBoardList)

    def _jsons(self, kind):
        files = self.directory.child(kind).globChildren("*.json")
        for json_file in files:
            yield (json.load(json_file.open()), json_file)

    def _board_dir(self, board_name):
        return self.directory.child('boards').child(board_name)

    def _getJobForBoard(self, board_name):
        self.logger.debug('getting job for %s', board_name)
        board_dir = self._board_dir(board_name)
        if board_dir.listdir() != []:
            self.logger.debug('board %s busy', board_name)
            return None
        for json_data, json_file in self._jsons('incoming'):
            self.logger.debug('considering %s for %s', json_file, board_name)
            if json_data['target'] == board_name:
                self.logger.debug('running %s on %s', json_file, board_name)
                json_file.moveTo(board_dir.child(json_file.basename()))
                return json_data
        else:
            return None

    def getJobForBoard(self, board_name):
        return defer.maybeDeferred(self._getJobForBoard, board_name)

    def _jobCompleted(self, board_name, log_stream):
        [json_file] = self._board_dir(board_name).children()
        completed = self.directory.child('completed')
        counter = 0
        while True:
            fname = '%03d%s' % (counter, json_file.basename())
            if not completed.child(fname).exists():
                break
            counter += 1
        json_file.moveTo(completed.child(fname))

    def jobCompleted(self, board_name, log_stream):
        return defer.maybeDeferred(self._jobCompleted, board_name, log_stream)
