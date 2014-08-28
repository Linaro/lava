# Copyright (C) 2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
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
import bz2
import contextlib
import logging
import lzma
import os
import re
import subprocess
import time
import traceback
import urllib2
import urlparse
import zlib
import socket

from tempfile import mkdtemp
from lava_dispatcher.config import get_config_file
from lava_dispatcher.utils import rmtree
import hashlib


@contextlib.contextmanager
def _scp_stream(url, proxy=None, cookies=None):
    process = None
    try:
        process = subprocess.Popen(
            ['nice', 'ssh', url.netloc, 'cat', url.path],
            shell=False,
            stdout=subprocess.PIPE
        )
        yield process.stdout
    finally:
        if process:
            process.kill()


@contextlib.contextmanager
def _http_stream(url, proxy=None, cookies=None):
    resp = None
    handlers = []
    if proxy:
        handlers = [urllib2.ProxyHandler({'http': '%s' % proxy})]
    opener = urllib2.build_opener(*handlers)

    if cookies:
        opener.addheaders.append(('Cookie', cookies))

    try:
        url = urllib2.quote(url.geturl(), safe=":/")
        resp = opener.open(url, timeout=30)
        yield resp
    finally:
        if resp:
            resp.close()


@contextlib.contextmanager
def _file_stream(url, proxy=None, cookies=None):
    fd = None
    try:
        fd = open(url.path, 'rb')
        yield fd
    finally:
        if fd:
            fd.close()


@contextlib.contextmanager
def _decompressor_stream(url, imgdir, decompress):
    fd = None
    decompressor = None

    fname, suffix = _url_to_fname_suffix(url, imgdir)

    if suffix == 'gz' and decompress:
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif suffix == 'bz2' and decompress:
        decompressor = bz2.BZ2Decompressor()
    elif suffix == 'xz' and decompress:
        decompressor = lzma.LZMADecompressor()
    else:
        # don't remove the file's real suffix
        fname = '%s.%s' % (fname, suffix)

    def write(buff):
        if decompressor:
            buff = decompressor.decompress(buff)
        fd.write(buff)

    try:
        fd = open(fname, 'wb')
        yield (write, fname)
    finally:
        if fd:
            fd.close()


def _url_to_fname_suffix(url, path='/tmp'):
    filename = os.path.basename(url.path)
    parts = filename.split('.')
    suffix = parts[-1]
    filename = os.path.join(path, '.'.join(parts[:-1]))
    return filename, suffix


def _url_mapping(url, context):
    """allows the downloader to override a URL so that something like:
     http://blah/ becomes file://localhost/blah
    """
    mappings = get_config_file('urlmappings.txt')
    if mappings:
        newurl = url
        with open(mappings, 'r') as f:
            for line in f.readlines():
                pat, rep = line.split(',')
                pat = pat.strip()
                rep = rep.strip()
                newurl = re.sub(pat, rep, newurl)
        if newurl != url:
            url = newurl
            logging.info('url mapped to: %s', url)
    return url


def download_image(url_string, context, imgdir=None,
                   delete_on_exit=True, decompress=True, timeout=300):
    """downloads a image that's been compressed as .bz2 or .gz and
    optionally decompresses it on the file to the cache directory
    will retry if the download fails, default five minute timeout
    """
    logging.debug("About to download %s to the host" % url_string)
    now = time.time()
    tries = 0
    while True:
        try:
            logging.info("Downloading image: %s" % url_string)
            if not imgdir:
                imgdir = mkdtemp(dir=context.config.lava_image_tmpdir)
                if delete_on_exit:
                    atexit.register(rmtree, imgdir)

            url = _url_mapping(url_string, context)

            url = urlparse.urlparse(url)
            if url.scheme == 'scp':
                reader = _scp_stream
            elif url.scheme == 'http' or url.scheme == 'https':
                reader = _http_stream
            elif url.scheme == 'file':
                reader = _file_stream
            else:
                raise Exception("Unsupported url protocol scheme: %s" % url.scheme)

            cookies = context.config.lava_cookies
            with reader(url, context.config.lava_proxy, cookies) as r:
                with _decompressor_stream(url, imgdir, decompress) as (writer, fname):
                    md5 = hashlib.md5()
                    sha256 = hashlib.sha256()
                    bsize = 32768
                    buff = r.read(bsize)
                    md5.update(buff)
                    sha256.update(buff)
                    while buff:
                        writer(buff)
                        buff = r.read(bsize)
                        md5.update(buff)
                        sha256.update(buff)
            logging.info("md5sum of downloaded content: %s" % md5.hexdigest())
            logging.debug("sha256sum of downloaded content: %s" % sha256.hexdigest())

            if fname.endswith('.qcow2'):
                orig = fname
                fname = re.sub('\.qcow2$', '.img', fname)
                logging.warning("Converting downloaded image from qcow2 to raw")
                subprocess.check_call(['qemu-img', 'convert', '-f', 'qcow2',
                                       '-O', 'raw', orig, fname])

            return fname
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except (IOError, socket.error, socket.timeout,
                urllib2.HTTPError, urllib2.URLError) as e:
            if hasattr(e, 'reason'):
                if hasattr(e, 'code'):
                    logging.error("Unable to download '%s': %s %s" % (url_string, e.code, e.reason))
                else:
                    logging.error("Unable to download '%s': %s" % (url_string, e.reason))
            else:
                logging.error("Unable to download '%s': %s" % (url_string, e))
            tries += 1
            if time.time() >= now + timeout:
                raise RuntimeError(
                    'downloading %s failed after %d tries: %s' % (url_string, tries, e))
            else:
                logging.info('Sleep one minute and retry (%d)' % tries)
                time.sleep(60)
        # add other exceptions to the above section and then remove the broad clause
        except Exception as e:
            logging.warn("unable to download: %r" % traceback.format_exc())
            tries += 1
            if time.time() >= now + timeout:
                raise RuntimeError(
                    'downloading %s failed after %d tries: %s' % (url_string, tries, e))
            else:
                logging.info('Sleep one minute and retry (%d)' % tries)
                time.sleep(60)
