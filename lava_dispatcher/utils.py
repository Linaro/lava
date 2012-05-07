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

import datetime
import errno
import logging
import os
import shutil
import urllib2
import urlparse
from shlex import shlex

import pexpect


def download(url, path="", proxy=None, verbose_failure=1):
    urlpath = urlparse.urlsplit(url).path
    filename = os.path.basename(urlpath)
    if path:
        filename = os.path.join(path, filename)
    fd = open(filename, "w")
    try:
        if proxy:
            handlers = [urllib2.ProxyHandler({'http': '%s' % proxy})]
        else:
            handlers = []
        opener = urllib2.build_opener(*handlers)
        response = opener.open(urllib2.quote(url, safe=":/"), timeout=30)
        fd = open(filename, 'wb')
        shutil.copyfileobj(response, fd, 0x10000)
        fd.close()
        response.close()
    except:
        if verbose_failure:
            logging.exception("download '%s' failed" % url)
        raise RuntimeError("Could not retrieve %s" % url)
    return filename

# XXX: duplication, we have similar code in lava-test, we need to move that to
# lava.utils -> namespace as standalone package
# def download_with_cache(url, path="", cachedir=""):


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


# XXX Duplication: we should reuse lava-test TestArtifacts
def generate_bundle_file_name(test_name):
    return  ("{test_id}.{time.tm_year:04}-{time.tm_mon:02}-{time.tm_mday:02}T"
            "{time.tm_hour:02}:{time.tm_min:02}:{time.tm_sec:02}Z").format(
                test_id=test_name,
                time=datetime.datetime.utcnow().timetuple())
