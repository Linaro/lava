# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
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
# python2 only

import math
import os
import time
import urlparse
import hashlib
import requests
import subprocess
import bz2
import contextlib
import lzma
import zlib
from lava_dispatcher.pipeline.action import (
    Action,
    JobError,
    Pipeline,
)
from lava_dispatcher.pipeline.logical import RetryAction
from lava_dispatcher.pipeline.utils.constants import (
    FILE_DOWNLOAD_CHUNK_SIZE,
    HTTP_DOWNLOAD_CHUNK_SIZE,
    HTTP_DOWNLOAD_TIMEOUT,
    SCP_DOWNLOAD_CHUNK_SIZE,
)


# FIXME: separate download actions for decompressed and uncompressed downloads
# so that the logic can be held in the Strategy class, not the Action.
# FIXME: create a download3.py which uses urllib.urlparse

class DownloaderAction(RetryAction):
    """
    The retry pipeline for downloads.
    To allow any deploy action to work with multinode, each call *must* set a unique path.
    """
    def __init__(self, key, path):
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


class DownloadHandler(Action):  # pylint: disable=too-many-instance-attributes
    """
    The identification of which downloader and whether to
    decompress needs to be done in the validation stage,
    with the ScpAction or HttpAction or FileAction being
    selected as part of the deployment. All the information
    needed to make this selection is available before the
    job starts, so populate the pipeline as specifically
    as possible.
    """

    def __init__(self, key, path, url):
        super(DownloadHandler, self).__init__()
        self.name = "download_action"
        self.description = "download action"
        self.summary = "download-action"
        self.proxy = None
        self.url = url
        self.key = key
        self.path = path
        self.size = -1

    def reader(self):
        raise NotImplementedError

    def _url_to_fname_suffix(self, path, modify):
        filename = os.path.basename(self.url.path)
        parts = filename.split('.')
        suffix = parts[-1]
        if not modify:
            filename = os.path.join(path, filename)
            suffix = None
        elif len(parts) == 1:  # handle files without suffixes, e.g. kernel images
            filename = os.path.join(path, ''.join(parts[-1]))
            suffix = None
        else:
            filename = os.path.join(path, '.'.join(parts[:-1]))
        return filename, suffix

    @contextlib.contextmanager
    def _decompressor_stream(self):
        dwnld_file = None
        compression = self.parameters.get('compression', False)
        fname, _ = self._url_to_fname_suffix(self.path, compression)

        decompressor = None
        if compression:
            if compression == 'gz':
                decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
            elif compression == 'bz2':
                decompressor = bz2.BZ2Decompressor()
            elif compression == 'xz':
                decompressor = lzma.LZMADecompressor()  # pylint: disable=no-member
            self.logger.debug("Using %s decompression" % compression)
        else:
            self.logger.debug("No compression specified.")

        def write(buff):
            if decompressor:
                buff = decompressor.decompress(buff)
            dwnld_file.write(buff)

        try:
            dwnld_file = open(fname, 'wb')
            yield (write, fname)
        finally:
            if dwnld_file:
                dwnld_file.close()

    def validate(self):
        super(DownloadHandler, self).validate()
        self.url = urlparse.urlparse(self.parameters[self.key])
        compression = self.parameters.get('compression', False)
        fname, _ = self._url_to_fname_suffix(self.path, compression)

        self.data.setdefault('download_action', {self.key: {}})
        self.data['download_action'][self.key] = {'file': fname}

        if compression:
            if compression not in ['gz', 'bz2', 'xz']:
                self.errors = "Unknown 'compression' format '%s'" % compression

    def run(self, connection, args=None):
        def progress_unknown_total(downloaded_size, last_value):
            """ Compute progress when the size is unknown """
            condition = downloaded_size >= last_value + 25 * 1024 * 1024
            return (condition, downloaded_size,
                    "progress %dMB" % (int(downloaded_size / (1024 * 1024))) if condition else "")

        def progress_known_total(downloaded_size, last_value):
            """ Compute progress when the size is known """
            percent = math.floor(downloaded_size / float(self.size) * 100)
            condition = percent >= last_value + 5
            return (condition, percent,
                    "progress %3d%% (%dMB)" % (percent, int(downloaded_size / (1024 * 1024))) if condition else "")

        connection = super(DownloadHandler, self).run(connection, args)
        # self.cookies = self.job.context.config.lava_cookies  # FIXME: work out how to restore
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        with self._decompressor_stream() as (writer, fname):
            self.logger.info("downloading %s as %s" % (self.parameters[self.key], fname))

            downloaded_size = 0
            beginning = time.time()
            # Choose the progress bar (is the size known?)
            if self.size == -1:
                self.logger.debug("total size: unknown")
                last_value = -25 * 1024 * 1024
                progress = progress_unknown_total
            else:
                self.logger.debug("total size: %d (%dMB)" % (self.size, int(self.size / (1024 * 1024))))
                last_value = -5
                progress = progress_known_total

            # Download the file and log the progresses
            for buff in self.reader():
                downloaded_size += len(buff)
                (printing, new_value, msg) = progress(downloaded_size, last_value)
                if printing:
                    last_value = new_value
                    self.logger.debug(msg)
                md5.update(buff)
                sha256.update(buff)
                writer(buff)

            # Log the download speed
            ending = time.time()
            self.logger.info("%dMB downloaded in %0.2fs (%0.2fMB/s)" %
                             (downloaded_size / (1024 * 1024), round(ending - beginning, 2),
                              round(downloaded_size / (1024 * 1024 * (ending - beginning)), 2)))

        # set the dynamic data into the context
        self.data['download_action'][self.key] = {
            'file': fname,
            'md5': md5.hexdigest(),
            'sha256': sha256.hexdigest()
        }
        # certain deployments need prefixes set
        if self.parameters['to'] == 'tftp':
            suffix = self.data['tftp-deploy'].get('suffix', '')
            self.set_common_data('file', self.key, os.path.join(suffix, os.path.basename(fname)))
        else:
            self.set_common_data('file', self.key, fname)
        self.logger.info("md5sum of downloaded content: %s" % (md5.hexdigest()))
        self.logger.info("sha256sum of downloaded content: %s" % (sha256.hexdigest()))
        return connection


class FileDownloadAction(DownloadHandler):
    """
    Download a resource from file (copy)
    """

    def __init__(self, key, path, url):
        super(FileDownloadAction, self).__init__(key, path, url)
        self.name = "file_download"
        self.description = "copy a local file"
        self.summary = "local file copy"

    def validate(self):
        super(FileDownloadAction, self).validate()
        try:
            self.size = os.stat(self.url.path).st_size
        except OSError:
            self.errors = "Image file '%s' does not exist or is not readable" % (self.url.path)

    def reader(self):
        reader = None
        try:
            reader = open(self.url.path, 'rb')
            buff = reader.read(FILE_DOWNLOAD_CHUNK_SIZE)
            while buff:
                yield buff
                buff = reader.read(FILE_DOWNLOAD_CHUNK_SIZE)
        except IOError as exc:
            # TODO: improve error message
            raise JobError(exc)
        finally:
            if reader is not None:
                reader.close()


class HttpDownloadAction(DownloadHandler):
    """
    Download a resource over http or https using requests module
    """

    def __init__(self, key, path, url):
        super(HttpDownloadAction, self).__init__(key, path, url)
        self.name = "http_download"
        self.description = "use http to download the file"
        self.summary = "http download"

    def validate(self):
        super(HttpDownloadAction, self).validate()
        try:
            res = requests.head(self.url.geturl(), allow_redirects=True, timeout=HTTP_DOWNLOAD_TIMEOUT)
            if res.status_code != requests.codes.OK:  # pylint: disable=no-member
                self.errors = "Resources not available at '%s'" % (self.url.geturl())
            else:
                self.size = int(res.headers.get('content-length', -1))
        except requests.Timeout:
            self.errors = "'%s' timed out" % (self.url.geturl())
        except requests.RequestException as exc:
            # TODO: find a better way to report the error
            self.errors = str(exc)

    def reader(self):
        res = None
        try:
            res = requests.get(self.url.geturl(), allow_redirects=True, stream=True, timeout=HTTP_DOWNLOAD_TIMEOUT)
            if res.status_code != requests.codes.OK:  # pylint: disable=no-member
                raise JobError("Unable to download '%s'" % (self.url.geturl()))
            for buff in res.iter_content(HTTP_DOWNLOAD_CHUNK_SIZE):
                yield buff
        except requests.RequestException as exc:
            # TODO: improve error reporting
            raise JobError(exc)
        finally:
            if res is not None:
                res.close()


class ScpDownloadAction(DownloadHandler):
    """
    Download a resource over scp
    """

    def __init__(self, key, path, url):
        super(ScpDownloadAction, self).__init__(key, path, url)
        self.name = "scp_download"
        self.description = "Use scp to copy the file"
        self.summary = "scp download"

    def validate(self):
        super(ScpDownloadAction, self).validate()
        try:
            size = subprocess.check_output(['nice', 'ssh',
                                            self.url.netloc,
                                            'stat', '-c', '%s',
                                            self.url.path],
                                           stderr=subprocess.STDOUT)
            self.size = int(size)
        except subprocess.CalledProcessError as exc:
            self.errors = str(exc)

    def reader(self):
        process = None
        try:
            process = subprocess.Popen(
                ['nice', 'ssh', self.url.netloc, 'cat', self.url.path],
                stdout=subprocess.PIPE
            )
            buff = process.stdout.read(SCP_DOWNLOAD_CHUNK_SIZE)
            while buff:
                yield buff
                buff = process.stdout.read(SCP_DOWNLOAD_CHUNK_SIZE)
            if process.wait() != 0:
                raise JobError("Dowloading '%s' failed with message '%s'"
                               % (self.url.geturl(), process.stderr.read()))
        finally:
            if process is not None:
                try:
                    process.kill()
                except OSError:
                    pass


class QCowConversionAction(Action):
    """
    explicit action for qcow conversion to avoid reliance
    on filename suffix
    """

    def __init__(self, key):
        super(QCowConversionAction, self).__init__()
        self.name = "qcow2_convert"
        self.description = "convert qcow image using qemu-img"
        self.summary = "qcow conversion"
        self.key = key

    def run(self, connection, args=None):
        if self.key not in self.data['download_action']:
            raise RuntimeError("'download_action.%s' missing in the context" % self.key)
        connection = super(QCowConversionAction, self).run(connection, args)
        fname = self.data['download_action'][self.key]['file']
        origin = fname
        # Change the extension only if the file ends with '.qcow2'
        if fname.endswith('.qcow2'):
            fname = fname[:-5] + "img"
        else:
            fname += ".img"

        self.logger.debug("Converting downloaded image from qcow2 to raw")
        subprocess.check_call(['qemu-img', 'convert', '-f', 'qcow2',
                               '-O', 'raw', origin, fname])
        self.data['download_action'][self.key]['file'] = fname
        self.set_common_data('file', self.key, fname)
        return connection
