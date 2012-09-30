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
import select
import sys
import shutil
import tempfile
import urlparse
from shlex import shlex

import pexpect


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


def mkdtemp(basedir='/tmp'):
    ''' returns a temporary directory that's deleted when the process exits
    '''

    d = tempfile.mkdtemp(dir=basedir)
    atexit.register(shutil.rmtree, d)
    os.chmod(d, 0755)
    return d


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


class logging_spawn(pexpect.spawn):

    def sendline(self, *args, **kw):
        logging.debug("sendline : %s" % args[0])
        return super(logging_spawn, self).sendline(*args, **kw)

    def send(self, *args, **kw):
        logging.debug("send : %s" % args[0])
        return super(logging_spawn, self).send(*args, **kw)

    def expect(self, *args, **kw):
        # some expect should not be logged because it is so much noise.
        if 'lava_no_logging' in  kw:
            del kw['lava_no_logging']
            return self.expect(*args, **kw)

        if 'timeout' in kw:
            timeout = kw['timeout']
        else:
            timeout = self.timeout

        if len(args) == 1:
            logging.debug("expect (%d): '%s'" % (timeout, args[0]))
        else:
            logging.debug("expect (%d): '%s'" % (timeout, str(args)))

        return super(logging_spawn, self).expect(*args, **kw)

    def drain(self):
        """this is a one-off of the pexect __interact that ignores STDIN and
        handles an error that happens when we call read just after the process exits
        """
        try:
            self._spawn__interact_copy(escape_character=chr(29))
        except:
            einfo = sys.exc_info()
            # since we blindly read this from a thread, it will always wind up
            # dying with a select error. we should still make note of other
            # exceptions that might happen
            if not isinstance(einfo[1], select.error):
                logging.warn("error while draining pexpect buffers: %r", einfo)
            pass


# XXX Duplication: we should reuse lava-test TestArtifacts
def generate_bundle_file_name(test_name):
    return  ("{test_id}.{time.tm_year:04}-{time.tm_mon:02}-{time.tm_mday:02}T"
            "{time.tm_hour:02}:{time.tm_min:02}:{time.tm_sec:02}Z").format(
                test_id=test_name,
                time=datetime.datetime.utcnow().timetuple())
