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

# This class is used for all downloads, including images and individual files for tftp.

import os
import urlparse
import hashlib
import requests
import subprocess  # FIXME: should not need this
import bz2
import contextlib
import lzma
import zlib
from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
    Pipeline,
    RetryAction,
)

# FIXME: separate download actions for decompressed and uncompressed downloads
# so that the logic can be held in the Strategy class, not the Action.


class DownloaderAction(RetryAction):
    """
    The retry pipeline for downloads.
    """
    def __init__(self, key, path="/tmp"):
        super(DownloaderAction, self).__init__()
        self.name = "download_retry"
        self.description = "download with retry"
        self.summary = "download-retry"
        self.key = key  # the key in the parameters of what to download
        self.path = path  # where to download

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        # Find the right action according to the url
        url = urlparse.urlparse(parameters[self.key])
        if url.scheme == 'scp':
            action = ScpDownloadAction(self.key, self.path, url)
        elif url.scheme == 'http' or url.scheme == 'https':
            action = HttpDownloadAction(self.key, self.path, url)
        elif url.scheme == 'file':
            action = FileDownloadAction(self.key, self.path, url)
        else:
            raise JobError("Unsupported url protocol scheme: %s" % url.scheme)
        self.internal_pipeline.add_action(action)


class DownloadHandler(Action):
    """
    The identification of which downloader and whether to
    decompress needs to be done in the validation stage,
    with the ScpAction or HttpAction or FileAction being
    selected as part of the deployment. All the information
    needed to make this selection is available before the
    job starts, so populate the pipeline as specifically
    as possible.
    """

    # FIXME: ensure that a useful progress indicator is used for all downloads., e.g. every 5%
    def __init__(self, key, path, url):
        super(DownloadHandler, self).__init__()
        self.name = "download_action"
        self.description = "download action"
        self.summary = "download-action"
        self.proxy = None
        self.url = url
        self.key = key
        self.path = path

# FIXME: replace by utils.download
    @contextlib.contextmanager
    def _scp_stream(self):
        process = None
        url = self.parameters[self.key]
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

    def _url_to_fname_suffix(self, path):
        filename = os.path.basename(self.url.path)
        parts = filename.split('.')
        suffix = parts[-1]
        if len(parts) == 1:  # handle files without suffixes, e.g. kernel images
            filename = os.path.join(path, ''.join(parts[-1]))
            suffix = None
        else:
            filename = os.path.join(path, '.'.join(parts[:-1]))
        return filename, suffix

    @contextlib.contextmanager
    def _decompressor_stream(self):
        # FIXME: should decompression be a different DownloadAction?
        fd = None
        decompressor = None
        decompress = False
        if self.key == 'image':
            decompress = True  # FIXME: get from job.parameters

        fname, suffix = self._url_to_fname_suffix(self.path)  # FIXME: use the context tmpdir

        if suffix == 'gz' and decompress:
            decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        elif suffix == 'bz2' and decompress:
            decompressor = bz2.BZ2Decompressor()
        elif suffix == 'xz' and decompress:
            decompressor = lzma.LZMADecompressor()
        elif suffix is not None:
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

    def validate(self):
        super(DownloadHandler, self).validate()
        self.url = urlparse.urlparse(self.parameters[self.key])
        fname, suffix = self._url_to_fname_suffix(self.path)  # FIXME: use the context tmpdir

        self.data.setdefault('download_action', {self.key: {}})
        self.data['download_action'].update({self.key: {'file': fname}})

    def run(self, connection, args=None):
        # self.cookies = self.job.context.config.lava_cookies  # FIXME: work out how to restore
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        with self._decompressor_stream() as (writer, fname):
            self._log("downloading and decompressing %s as %s" % (self.parameters[self.key], fname))

            # TODO: print the progress in the logs
            for buff in self.reader():
                md5.update(buff)
                sha256.update(buff)
                writer(buff)
        # set the dynamic data into the context
        self.data['download_action'][self.key] = {
            'file': fname,
            'md5': md5.hexdigest(),
            'sha256': sha256.hexdigest()
        }
        return connection


class FileDownloadAction(DownloadHandler):

    def __init__(self, key, path, url):
        super(FileDownloadAction, self).__init__(key, path, url)
        self.name = "file_download"
        self.description = "copy a local file"
        self.summary = "local file copy"

    def validate(self):
        super(FileDownloadAction, self).validate()
        if not os.path.isfile(self.url.path):
            self.errors = "Image file '%s' does not exists" % (self.url.path)

    def reader(self):
        try:
            fd = open(self.url.path, 'rb')
            buff = fd.read(32768)
            while buff:
                yield buff
                buff = fd.read(32768)
        except IOError as exc:
            # TODO: improve error message
            raise JobError(exc)
        finally:
            if fd:
                fd.close()


class HttpDownloadAction(DownloadHandler):

    def __init__(self, key, path, url):
        super(HttpDownloadAction, self).__init__(key, path, url)
        self.name = "http_download"
        self.description = "use http to download the file"
        self.summary = "http download"

    def validate(self):
        super(HttpDownloadAction, self).validate()
        try:
            # TODO: move the constant in a specific module
            res = requests.head(self.url.geturl(), allow_redirects=True, timeout=15)
            if res.status_code != requests.codes.OK:
                self.errors = "Resources not available at '%s'" % (self.url.geturl())
        except requests.Timeout:
            self.errors = "'%s' timed out" % (self.url.geturl())
        except requests.RequestException as exc:
            # TODO: find a better way to report the error
            self.errors = exc

    def reader(self):
        try:
            res = requests.get(self.url.geturl(), allow_redirects=True, stream=True, timeout=15)
            if res.status_code != requests.codes.OK:
                raise JobError("Unable to download '%s'" % (self.url.geturl()))
            for buff in res.iter_content(32768):
                yield buff
        except requests.RequestException as exc:
            # TODO: improve error reporting
            raise JobError(exc)
        finally:
            res.close()


class ScpDownloadAction(DownloadHandler):

    def __init__(self, key, path, url):
        super(ScpDownloadAction, self).__init__(key, path, url)
        self.name = "scp_download"
        self.description = "Use scp to copy the file"
        self.summary = "scp download"

    def validate(self):
        raise NotImplementedError()

    def reader(self):
        raise NotImplementedError()

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


class ChecksumAction(Action):  # FIXME: fold into the DownloadHandler
    """
    retrieves the checksums from the dynamic data
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
        # TODO: if the checksums are not present, compute them now
        return connection


class QCowConversionAction(Action):
    """
    explicit action for qcow conversion to avoid reliance
    on filename suffix
    """

    def __init__(self, key):
        super(QCowConversionAction, self).__init__()
        self.name = "qcow2"
        self.description = "convert qcow image using qemu-img"
        self.summary = "qcow conversion"
        self.key = key

    def run(self, connection, args=None):
        if self.key not in self.data['download_action']:
            raise RuntimeError("'download_action.%s' missing in the context" % (self.key))

        fname = self.data['download_action'][self.key]['file']
        origin = fname
        # Change the extension only if the file ends with '.qcow2'
        if fname.endswith('.qcow2'):
            fname = fname[:-5] + "img"
        else:
            fname = fname + ".img"

        self._log("Converting downloaded image from qcow2 to raw")
        subprocess.check_call(['qemu-img', 'convert', '-f', 'qcow2',
                               '-O', 'raw', origin, fname])
        self.data['download_action'][self.key]['file'] = fname

        return connection
