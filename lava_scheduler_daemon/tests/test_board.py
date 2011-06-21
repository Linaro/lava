from twisted.internet import defer
from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase

from lava_scheduler_daemon.board import Board


class TestJobSource(object):

    def __init__(self):
        self.job_requests = {}

    def getJobForBoard(self, board_name):
        d = defer.Deferred()
        self.job_requests.setdefault(board_name, []).append(d)
        d.addBoth(self._remove_request, board_name, d)
        return d

    def _remove_request(self, result, board_name, d):
        self.job_requests[board_name].remove(d)
        return result


class TestJob(object):

    def __init__(self, json_data, dispatcher, reactor):
        self.json_data = json_data
        self.dispatcher = dispatcher
        self.reactor = reactor
        self.deferred = defer.Deferred()

    def run(self):
        return self.deferred

class TestBoard(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.clock = Clock()
        self.source = TestJobSource()

    def make_board(self, board_name):
        return Board(self.source, board_name, 'script', self.clock, TestJob)

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
        self.source.job_requests['board'][-1].callback(None)
        self.assertEqual('W', b._state_name())

    def test_actual_job_runs(self):
        b = self.make_board('board')
        b.start()
        self.source.job_requests['board'][-1].callback({})
        self.assertEqual('R', b._state_name())
