# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import os
import urlparse
import urllib2  # FIXME: use requests
import hashlib
import subprocess  # FIXME: should not need this
import bz2
import contextlib
import lzma
import zlib
from lava_dispatcher.pipeline.action import (
    Action,
    Pipeline,
    RetryAction,
)
from lava_dispatcher.context import LavaContext


class ScpDownloadAction(Action):

    def __init__(self):
        super(ScpDownloadAction, self).__init__()
        self.name = "scp_download"
        self.description = "Use scp to copy the file"
        self.summary = "scp download"

    @contextlib.contextmanager
    def run(self, connection, args=None):
        process = None
        url = self.parameters['image']
        try:
            # FIXME: adapt with code from self.run_command() for logging
            process = subprocess.Popen(
                ['nice', 'ssh', url.netloc, 'cat', url.path],
                shell=False,
                stdout=subprocess.PIPE
            )
            yield process.stdout
        finally:
            if process:
                process.kill()


class HttpDownloadAction(Action):

    def __init__(self):
        super(HttpDownloadAction, self).__init__()
        self.name = "http_download"
        self.description = "use http to download the file"
        self.summary = "http download"


class FileDownloadAction(Action):

    def __init__(self):
        super(FileDownloadAction, self).__init__()
        self.name = "file_download"
        self.description = "copy a local file"
        self.summary = "local file copy"


class DownloaderAction(RetryAction):
    """
    The identification of which downloader and whether to
    decompress needs to be done in the validation stage,
    with the ScpAction or HttpAction or FileAction being
    selected as part of the deployment. All the information
    needed to make this selection is available before the
    job starts, so populate the pipeline as specifically
    as possible.
    """

    def __init__(self):
        super(DownloaderAction, self).__init__()
        self.name = "download_action"
        self.description = "download with retry"
        self.summary = "download-retry"
        self.proxy = None
        self.url = None

    @contextlib.contextmanager
    def _scp_stream(self):
        process = None
        url = self.parameters['image']
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
    def _http_stream(self):
        resp = None
        handlers = []
        if self.proxy:  # FIXME: allow for this to be set from parameters
            handlers = [urllib2.ProxyHandler({'http': '%s' % self.proxy})]
        opener = urllib2.build_opener(*handlers)

        if self.cookies:
            opener.addheaders.append(('Cookie', self.cookies))

        try:
            url = urllib2.quote(self.url.geturl(), safe=":/")
            resp = opener.open(url, timeout=30)
            yield resp
        finally:
            if resp:
                resp.close()

    @contextlib.contextmanager
    def _file_stream(self):
        fd = None
        try:
            fd = open(self.url.path, 'rb')
            yield fd
        finally:
            if fd:
                fd.close()

    def _url_to_fname_suffix(self, path='/tmp'):
        filename = os.path.basename(self.url.path)
        parts = filename.split('.')
        suffix = parts[-1]
        filename = os.path.join(path, '.'.join(parts[:-1]))
        return filename, suffix

    @contextlib.contextmanager
    def _decompressor_stream(self):
        fd = None
        decompressor = None
        decompress = True  # FIXME: get from job.parameters

        fname, suffix = self._url_to_fname_suffix()  # FIXME: use the context tmpdir

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

    def parse(self):
        """
        Move to being part of the Deployment strategy
        so that only the correct action is added to the pipeline.
        """
        # FIXME use actions? check behaviour with contextmanager
        self.url = urlparse.urlparse(self.parameters['image'])
        if self.url.scheme == 'scp':
            self.reader = self._scp_stream
        elif self.url.scheme == 'http' or self.url.scheme == 'https':
            self.reader = self._http_stream
        elif self.url.scheme == 'file':
            self.reader = self._file_stream
        else:
            raise JobError("Unsupported url protocol scheme: %s" % url.scheme)

    def validate(self):
        self.parse()
        fname, suffix = self._url_to_fname_suffix()  # FIXME: use the context tmpdir
        if self.name not in self.data:
            self.data[self.name] = {}
        self.data[self.name]['file'] = fname

    def run(self, connection, args=None):
        self.parse()  # FIXME: do this in the deployment strategy
        self.cookies = self.job.context.config.lava_cookies
        fname, suffix = self._url_to_fname_suffix()  # FIXME: use the context tmpdir
        if os.path.exists(fname):
            self._log("development shortcut")  # TODO: remove
            return connection
        # The problem with the entire download method is that it
        # is completely hidden from the logs and the progress indicator.
        # Needs to switch to requests and give useful progress output.
        # if not, wget can do the right thing for http, https and file
        # and scp has progress built in too.
        with self.reader() as r:
            with self._decompressor_stream() as (writer, fname):
                self._log("downloading and decompressing %s as %s" % (self.parameters['image'], fname))
                self.md5 = hashlib.md5()
                self.sha256 = hashlib.sha256()
                bsize = 32768
                buff = r.read(bsize)
                self.md5.update(buff)
                self.sha256.update(buff)
                while buff:
                    writer(buff)
                    buff = r.read(bsize)
                    self.md5.update(buff)
                    self.sha256.update(buff)
        # FIXME: needs to raise JobError on 404 etc. for retry to operate
        # set the dynamic data into the context:
        # the decompressed filename and path
        self.data[self.name] = {
            'file': fname,
            'md5': self.md5.hexdigest(),
            'sha256': self.sha256.hexdigest()
        }
        return connection


class ChecksumAction(Action):
    """
    retrieves the checksums from the dynamic data
    *this may be folded into download*
    """

    def __init__(self):
        super(ChecksumAction, self).__init__()
        self.name = "checksum_action"
        self.description = "md5sum and sha256sum"
        self.summary = "checksum"

    def run(self, connection, args=None):
        if 'download_action' in self.data:
            if 'md5' in self.data['download_action']:
                self._log("md5sum of downloaded content: %s" %
                          self.data['download_action']['md5'])
            if 'sha256' in self.data['download_action']:
                self._log("sha256sum of downloaded content: %s" %
                          self.data['download_action']['sha256'])
        return connection


class QCowConversionAction(Action):
    """
    explicit action for qcow conversion to avoid reliance
    on filename suffix
    """

    def __init__(self):
        super(QCowConversionAction, self).__init__()
        self.name = "qcow2"
        self.description = "convert qcow image using qemu-img"
        self.summary = "qcow conversion"

    def run(self, connection, args=None):
        pass
#        if fname.endswith('.qcow2'):
#            orig = fname
#            fname = re.sub('\.qcow2$', '.img', fname)
#            logging.warning("Converting downloaded image from qcow2 to raw")
#            subprocess.check_call(['qemu-img', 'convert', '-f', 'qcow2',
#                                   '-O', 'raw', orig, fname])
