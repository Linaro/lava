from collections import defaultdict
import logging

from twisted.internet import defer
from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase

from lava_scheduler_daemon.board import Board

def stub_method(method_name):
    def method_impl(self, board_name, *args):
        assert method_name not in self._requests[board_name], (
            'overlapping call to %s on %s' % (method_name, board_name))
        d = self._requests[method_name][board_name] = defer.Deferred()
        def _remove_request(result):
            del self._requests[method_name][board_name]
            return result
        d.addBoth(_remove_request)
        self._calls[board_name][method_name].append(args)
        return d
    return method_impl


class TestJobSource(object):

    def __init__(self):
        self._calls = defaultdict(lambda :defaultdict(list))
        self._requests = defaultdict(dict)

    jobCompleted = stub_method('jobCompleted')
    getJobForBoard = stub_method('getJobForBoard')

    def _completeCall(self, method_name, board_name, result):
        self._requests[method_name][board_name].callback(result)


class TestJob(object):

    def __init__(self, job_data, dispatcher, source, board_name, reactor):
        self.json_data = job_data
        self.dispatcher = dispatcher
        self.reactor = reactor
        self.source = source
        self.board_name = board_name
        self.deferred = defer.Deferred()

    def run(self):
        return self.deferred


class AppendingHandler(logging.Handler):

    def __init__(self, target_list):
        logging.Handler.__init__(self)
        self.target_list = target_list

    def emit(self, record):
        self.target_list.append((record.levelno, self.format(record)))


class TestBoard(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.clock = Clock()
        self.source = TestJobSource()
        self._log_messages = []
        self._handler = AppendingHandler(self._log_messages)
        self.addCleanup(self._checkNoLogs)

    def _checkNoLogs(self):
        warnings = [message for (level, message) in self._log_messages
                    if level >= logging.WARNING]
        if warnings:
            self.fail("Logged warnings: %s" % warnings)

    def make_board(self, board_name):
        board = Board(self.source, board_name, 'script', self.clock, TestJob)
        board.logger.addHandler(self._handler)
        board.logger.setLevel(logging.DEBUG)
        return board

    def test_initial_state_is_stopped(self):
        b = self.make_board('board')
        self.assertEqual('S', b._state_name())

    def test_start_checks(self):
        b = self.make_board('board')
        b.start()
        self.assertEqual('C', b._state_name())

    def test_no_job_waits(self):
        b = self.make_board('board')
        b.start()
        self.source._completeCall('getJobForBoard', 'board', None)
        self.assertEqual('W', b._state_name())

    def test_actual_job_runs(self):
        b = self.make_board('board')
        b.start()
        self.source._completeCall('getJobForBoard', 'board', ({}, None))
        self.assertEqual('R', b._state_name())

    def test_check_again_on_completion(self):
        b = self.make_board('board')
        b.start()
        self.source._completeCall('getJobForBoard', 'board', ({}, None))
        b.running_job.deferred.callback('path')
        self.assertEqual('C', b._state_name())

    def test_stop_while_checking_moves_to_check_plus_stop(self):
        b = self.make_board('board')
        b.start()
        b.stop()
        self.assertEqual('C+S', b._state_name())

    def test_stop_while_checking_no_job_stops(self):
        b = self.make_board('board')
        b.start()
        s = b.stop()
        stop_results = []
        s.addCallback(stop_results.append)
        self.assertEqual(0, len(stop_results))
        self.source._completeCall('getJobForBoard', 'board', None)
        self.assertEqual(1, len(stop_results))
        self.assertEqual('S', b._state_name())

    def test_stop_while_checking_actual_job_runs(self):
        b = self.make_board('board')
        b.start()
        s = b.stop()
        stop_results = []
        s.addCallback(stop_results.append)
        self.assertEqual(0, len(stop_results))
        self.source._completeCall('getJobForBoard', 'board', ({}, None))
        self.assertEqual(0, len(stop_results))
        self.assertEqual('R+S', b._state_name())

    def test_stop_while_checking_actual_job_stops_on_complete(self):
        b = self.make_board('board')
        b.start()
        s = b.stop()
        stop_results = []
        s.addCallback(stop_results.append)
        self.assertEqual(0, len(stop_results))
        self.source._completeCall('getJobForBoard', 'board', ({}, None))
        b.running_job.deferred.callback(None)
        self.assertEqual(1, len(stop_results))
        self.assertEqual('S', b._state_name())

    def test_stop_while_running_job_stops_on_complete(self):
        b = self.make_board('board')
        b.start()
        self.source._completeCall('getJobForBoard', 'board', ({}, None))
        self.assertEqual('R', b._state_name())
        s = b.stop()
        stop_results = []
        s.addCallback(stop_results.append)
        self.assertEqual(0, len(stop_results))
        b.running_job.deferred.callback(None)
        self.assertEqual(1, len(stop_results))
        self.assertEqual('S', b._state_name())

    def test_wait_expires_check_again(self):
        b = self.make_board('board')
        b.start()
        self.source._completeCall('getJobForBoard', 'board', None)
        self.clock.advance(10000) # hack: the delay should be config data
        self.assertEqual('C', b._state_name())
