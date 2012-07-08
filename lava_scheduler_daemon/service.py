import logging

from twisted.application.service import Service
from twisted.internet import defer
from twisted.internet.task import LoopingCall

from lava_scheduler_daemon.board import Board, catchall_errback


class BoardSet(Service):

    def __init__(self, source, dispatcher, reactor, daemon_options):
        self.logger = logging.getLogger(__name__ + '.BoardSet')
        self.source = source
        self.boards = {}
        self.dispatcher = dispatcher
        self.reactor = reactor
        self.daemon_options = daemon_options
        self._update_boards_call = LoopingCall(self._updateBoards)
        self._update_boards_call.clock = reactor

    def _updateBoards(self):
        self.logger.debug("Refreshing board list")
        return self.source.getBoardList().addCallback(
            self._cbUpdateBoards).addErrback(catchall_errback(self.logger))

    def _cbUpdateBoards(self, board_cfgs):
        '''board_cfgs is an array of dicts {hostname=name, use_celery=...} '''
        new_boards = {}
        for board_cfg in board_cfgs:
            board_name = board_cfg['hostname']
            use_celery = board_cfg['use_celery']

            if board_cfg['hostname'] in self.boards:
                board = self.boards.pop(board_name)
                if use_celery != board.use_celery:
                    board.use_celery = use_celery
                    self.logger.info("use_celery changed for %s to '%s'" % \
                        (board_name, use_celery))
                new_boards[board_name] = board
            else:
                self.logger.info("Adding board: %s" % board_name)
                new_boards[board_name] = Board(
                    self.source, board_name, self.dispatcher, self.reactor,
                    self.daemon_options, use_celery)
                new_boards[board_name].start()
        for board in self.boards.values():
            self.logger.info("Removing board: %s" % board.board_name)
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


