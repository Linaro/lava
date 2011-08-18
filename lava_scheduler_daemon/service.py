import logging

from twisted.application.service import Service
from twisted.internet import defer
from twisted.internet.task import LoopingCall

from lava_scheduler_daemon.board import Board, catchall_errback


class BoardSet(Service):

    logger = logging.getLogger(__name__ + '.BoardSet')

    def __init__(self, source, dispatcher, reactor):
        self.source = source
        self.boards = {}
        self.dispatcher = dispatcher
        self.reactor = reactor
        self._update_boards_call = LoopingCall(self._updateBoards)
        self._update_boards_call.clock = reactor

    def _updateBoards(self):
        self.logger.debug("Refreshing board list")
        return self.source.getBoardList().addCallback(
            self._cbUpdateBoards).addErrback(catchall_errback(self.logger))

    def _cbUpdateBoards(self, board_names):
        if set(board_names) == set(self.boards):
            return
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
        dead_boards = []
        for board in self.boards.itervalues():
            ds.append(board.stop().addCallback(dead_boards.append))
        self.logger.info(
            "waiting for %s boards", len(self.boards) - len(dead_boards))
        return defer.gatherResults(ds)


