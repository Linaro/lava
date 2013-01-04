# Copyright (C) 2011-2012 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import atexit
import datetime
import errno
import logging
import os
import shutil
import tempfile
import threading
import time
import urlparse
import subprocess

from shlex import shlex

import pexpect

from lava_dispatcher.errors import CriticalError


def link_or_copy_file(src, dest):
    try:
        dir = os.path.dirname(dest)
        if not os.path.exists(dir):
            os.makedirs(dir)
        os.link(src, dest)
    except OSError, err:
        if err.errno == errno.EXDEV:
            shutil.copy(src, dest)
        if err.errno == errno.EEXIST:
            logging.debug("Cached copy of %s already exists" % dest)
        else:
            logging.exception("os.link '%s' with '%s' failed" % (src, dest))


def copy_file(src, dest):
    dir = os.path.dirname(dest)
    if not os.path.exists(dir):
        os.makedirs(dir)
    shutil.copy(src, dest)


def rmtree(directory):
    subprocess.call(['rm', '-rf', directory])


def mkdtemp(basedir='/tmp'):
    """ returns a temporary directory that's deleted when the process exits
    """

    d = tempfile.mkdtemp(dir=basedir)
    atexit.register(rmtree, d)
    os.chmod(d, 0755)
    return d


def mk_targz(tfname, rootdir, basedir='.', asroot=False):
    """ Similar shutil.make_archive but it doesn't blow up with unicode errors
    """
    cmd = 'tar -C %s -czf %s %s' % (rootdir, tfname, basedir)
    if asroot:
        cmd = 'sudo %s' % cmd
    if logging_system(cmd):
        raise CriticalError('Unable to make tarball of: %s' % rootdir)


def _list_files(dirname):
    files = []
    for f in os.listdir(dirname):
        f = os.path.join(dirname, f)
        if os.path.isdir(f):
            files.extend(_list_files(f))
        elif os.path.isfile(f):
            files.append(f)
    return files


def extract_targz(tfname, tmpdir):
    """ Extracts the contents of a .tgz file to the tmpdir. It then returns
    a list of all the files (full path). This is being used to get around
    issues that python's tarfile seems to have with unicode
    """
    if logging_system('tar -C %s -xzf %s' % (tmpdir, tfname)):
        raise CriticalError('Unable to extract tarball: %s' % tfname)

    return _list_files(tmpdir)


def ensure_directory(path):
    """ ensures the path exists, if it doesn't it will be created
    """
    if not os.path.exists(path):
        os.mkdir(path)


def ensure_directory_empty(path):
    """ Ensures the given directorty path exists, and is empty. It will delete
    The directory contents if needed.
    """
    if os.path.exists(path):
        rmtree(path)
    os.mkdir(path)


def url_to_cache(url, cachedir):
    url_parts = urlparse.urlsplit(url)
    path = os.path.join(cachedir, url_parts.netloc,
        url_parts.path.lstrip(os.sep))
    return path


def string_to_list(string):
    splitter = shlex(string, posix=True)
    splitter.whitespace = ","
    splitter.whitespace_split = True
    newlines_to_spaces = lambda x: x.replace('\n', ' ')
    strip_newlines = lambda x: newlines_to_spaces(x).strip(' ')
    return map(strip_newlines, list(splitter))


def logging_system(cmd):
    logging.debug("Executing on host : '%r'" % cmd)
    return os.system(cmd)


class DrainConsoleOutput(threading.Thread):

    def __init__(self, proc=None, timeout=None):
        threading.Thread.__init__(self)
        self.proc = proc
        self.timeout = timeout
        self._stopevent = threading.Event()
        self.daemon = True  # allow thread to die when main main proc exits

    def run(self):
        expect_end = None
        if self.timeout and (self.timeout > -1):
            expect_end = time.time() + self.timeout
        while not self._stopevent.isSet():
            if expect_end and (expect_end <= time.time()):
                logging.info("DrainConsoleOutput times out:%s" % self.timeout)
                break
            self.proc.empty_buffer()
            time.sleep(5)

    def join(self, timeout=None):
        self._stopevent.set()
        threading.Thread.join(self, timeout)


class logging_spawn(pexpect.spawn):

    def __init__(self, command, timeout=30, logfile=None):
        pexpect.spawn.__init__(
            self, command, timeout=timeout, logfile=logfile)

        # serial can be slow, races do funny things, so increase delay
        self.delaybeforesend = 0.05

    def sendline(self, s=''):
        logging.debug("sendline : %s", s)
        return super(logging_spawn, self).sendline(s)

    def send(self, string):
        logging.debug("send : %s", string)
        sent = 0
        for char in string:
            sent += super(logging_spawn, self).send(char)
        return sent

    def expect(self, *args, **kw):
        # some expect should not be logged because it is so much noise.
        if 'lava_no_logging' in kw:
            del kw['lava_no_logging']
            return self.expect(*args, **kw)

        if 'timeout' in kw:
            timeout = kw['timeout']
        else:
            timeout = self.timeout

        if len(args) == 1:
            logging.debug("expect (%d): '%s'", timeout, args[0])
        else:
            logging.debug("expect (%d): '%s'", timeout, str(args))

        return super(logging_spawn, self).expect(*args, **kw)

    def empty_buffer(self):
        """Make sure there is nothing in the pexpect buffer."""
        index = 0
        while index == 0:
            index = self.expect(
                ['.+', pexpect.EOF, pexpect.TIMEOUT],
                timeout=1, lava_no_logging=1)


def connect_to_serial(device_config, sio):
    """
    Attempts to connect to a serial console server like conmux or cyclades
    """
    retry_count = 0
    retry_limit = 3

    port_stuck_message = 'Data Buffering Suspended\.'
    conn_closed_message = 'Connection closed by foreign host\.'

    expectations = {
        port_stuck_message: 'reset-port',
        'Connected\.\r': 'all-good',
        conn_closed_message: 'retry',
        pexpect.TIMEOUT: 'all-good',
    }
    patterns = []
    results = []
    for pattern, result in expectations.items():
        patterns.append(pattern)
        results.append(result)

    while retry_count < retry_limit:
        proc = logging_spawn(device_config.connection_command, timeout=1200)
        proc.logfile_read = sio
        logging.info('Attempting to connect to device')
        match = proc.expect(patterns, timeout=10)
        result = results[match]
        logging.info('Matched %r which means %s', patterns[match], result)
        if result == 'retry':
            proc.close(True)
            retry_count += 1
            time.sleep(5)
            continue
        elif result == 'all-good':
            atexit.register(proc.close, True)
            return proc
        elif result == 'reset-port':
            reset_cmd = device_config.reset_port_command
            if reset_cmd:
                logging_system(reset_cmd)
            else:
                raise CriticalError('no reset_port command configured')
            proc.close(True)
            retry_count += 1
            time.sleep(5)
    raise CriticalError('could execute connection_command successfully')


# XXX Duplication: we should reuse lava-test TestArtifacts
def generate_bundle_file_name(test_name):
    return ("{test_id}.{time.tm_year:04}-{time.tm_mon:02}-{time.tm_mday:02}T"
            "{time.tm_hour:02}:{time.tm_min:02}:{time.tm_sec:02}Z").format(
                test_id=test_name,
                time=datetime.datetime.utcnow().timetuple())
