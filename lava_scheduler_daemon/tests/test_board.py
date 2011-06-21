from twisted.internet.task import Clock
from twisted.trial.unittest import TestCase

from lava_scheduler_daemon.board import Board

class TestBoard(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.clock = Clock()

    def test_initial_state_is_stopped(self):
        b = Board(None, 'board', 'script', self.clock)
        self.assertEqual('S', b._state_name())
