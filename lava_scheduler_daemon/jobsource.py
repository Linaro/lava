import json
import logging

from twisted.internet import defer

from zope.interface import (
    implements,
    Interface,
    )

logger = logging.getLogger(__name__)


class IJobSource(Interface):

    def getBoardList():
        """Get the list of currently configured board names."""

    def getJobForBoard(board_name):
        """Return the json data of a job for board_name and a log file.

        The job should be marked as started before it is returned.
        """

    def jobCompleted(board_name):
        """Mark the job currently running on `board_name` as completed."""


class DirectoryJobSource(object):

    implements(IJobSource)

    logger = logging.getLogger(__name__ + '.DirectoryJobSource')

    def __init__(self, directory):
        self.directory = directory
        if not self.directory.isdir():
            self.logger.critical("%s is not a directory", self.directory)
            raise RuntimeError("%s must be a directory" % self.directory)
        boards = self.directory.child('boards')
        if not boards.isdir():
            self.logger.critical("%s is not a directory", boards)
            raise RuntimeError("%s must be a directory" % boards)
        for subdir in 'incoming', 'completed', 'broken':
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
                return json_data, open('/dev/null', 'w')
        else:
            return None

    def getJobForBoard(self, board_name):
        return defer.maybeDeferred(self._getJobForBoard, board_name)

    def _jobCompleted(self, board_name):
        [json_file] = self._board_dir(board_name).children()
        completed = self.directory.child('completed')
        counter = 0
        while True:
            fname = '%03d%s' % (counter, json_file.basename())
            if not completed.child(fname).exists():
                break
            counter += 1
        json_file.moveTo(completed.child(fname))

    def jobCompleted(self, board_name):
        return defer.maybeDeferred(self._jobCompleted, board_name)
