import json
import logging
import os
import tempfile

from twisted.application.service import Service
from twisted.internet.defer import Deferred
from twisted.internet.process import ProcessProtocol
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread


def defer_to_thread(func):
    def wrapper(*args, **kw):
        return deferToThread(func, *args, **kw)
    return wrapper


class DirectoryJobSource(Service):
    """
    A job source that looks in a directory.

    It looks for jobs (json files) in a subdirectory 'incoming' of the
    directory it is configured with.  Running jobs are moved to 'running' and
    completed jobs to 'completed'.
    """

    logger = logging.getLogger('DirectoryJobSource')

    def __init__(self, directory, polling_interval, scheduler_service):
        self.directory = directory
        self.polling_interval = polling_interval
        self.scheduler_service = scheduler_service
        self._call = LoopingCall(self.lookForJob)

    def startService(self):
        self._call.start(5)

    def stopService(self):
        self._call.stop()

    def lookForJob(self):
        self.logger.info("Looking for a jobs in %", self.directory)
        json_files = self.directory.child('incoming').globChildren("*.json")
        json_files.sort(key=lambda fp:fp.getModificationTime())
        busyBoards = self.busyBoards()
        for json_file in json_files:
            json_data = json.load(json_files[0].open())
            if json_data['target'] not in busyBoards:
                self.scheduler_service.jobSubmitted(
                    json_data, json_file[0].basename())

    def markJobStarted(self, token):
        self.directory.child('incoming').child(token).moveTo(
            self.directory.child('running'))

    def markJobCompleted(self, token):
        self.directory.child('running').child(token).moveTo(
            self.directory.child('completed'))

    def _running_jsons(self):
        running_files = self.directory.child('running').globChildren("*.json")
        for json_file in running_files:
            yield (json.load(json_file.open()), json_file.basename())

    def busyBoards(self):
        return [json_data['target']
                for (json_data, token) in self._running_jsons()]

    def jobRunningOnBoard(self, hostname):
        for json_data, token in self._running_jsons:
            if json_data['target'] == hostname:
                return json_data, token
        else:
            return None


class DispatcherProcessProtocol(ProcessProtocol):

    def __init__(self, deferred):
        self.deferred = deferred
        fd, self._logpath = tempfile.mkstemp()

    def errReceived(self, text):
        pass

    def outReceived(self, text):
        pass

    def processEnded(self, reason):
        self.deferred.callback(None)


class LavaSchedulerService(Service):

    logger = logging.getLogger('LavaSchedulerService')

    def jobSubmitted(self, json_data, token):
        if json_data['target'] not in self.job_source.busyBoards():
            self._dispatchJob(json_data)
            self.job_source.markJobStarted(token)

    def jobCompleted(self, hostname):
        json_data, token = self.job_source.jobRunningOnBoard(hostname)
        self.job_source.markJobCompleted(token)

    def _dispatchJob(self, json_data):
        d = Deferred()
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as f:
            json_data.dump(f)
        def clean_up_file(result):
            self.logger.info("job finished on %s", json_data['target'])
            os.unlink(path)
            return result
        d.addBoth(clean_up_file)
        reactor.spawnProcess(
            DispatcherProcessProtocol(d), '/usr/bin/sleep',
            args=['/usr/bin/sleep', 2], childFDs={0:0, 1:1, 2:1})
