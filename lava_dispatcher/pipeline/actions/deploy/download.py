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

import errno
import math
import os
import sys
import shutil
import time
import hashlib
import requests
import subprocess
import bz2
import contextlib
import lzma
import zlib
from lava_dispatcher.pipeline.action import (
    Action,
    InfrastructureError,
    JobError,
    LAVABug,
    Pipeline,
)
from lava_dispatcher.pipeline.logical import RetryAction
from lava_dispatcher.pipeline.utils.compression import untar_file
from lava_dispatcher.pipeline.utils.constants import (
    FILE_DOWNLOAD_CHUNK_SIZE,
    HTTP_DOWNLOAD_CHUNK_SIZE,
    SCP_DOWNLOAD_CHUNK_SIZE,
)

if sys.version_info[0] == 2:
    import urlparse as lavaurl
elif sys.version_info[0] == 3:
    import urllib.parse as lavaurl  # pylint: disable=no-name-in-module,import-error

# pylint: disable=logging-not-lazy

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
        self.name = "download-retry"
        self.description = "download with retry"
        self.summary = "download-retry"
        self.max_retries = 3
        self.key = key  # the key in the parameters of what to download
        self.path = path  # where to download

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        # Find the right action according to the url
        if 'images' in parameters and self.key in parameters['images']:
            url = lavaurl.urlparse(parameters['images'][self.key]['url'])
        else:
            url = lavaurl.urlparse(parameters[self.key]['url'])
        if url.scheme == 'scp':
            action = ScpDownloadAction(self.key, self.path, url)
        elif url.scheme == 'http' or url.scheme == 'https':
            action = HttpDownloadAction(self.key, self.path, url)  # pylint: disable=redefined-variable-type
        elif url.scheme == 'file':
            action = FileDownloadAction(self.key, self.path, url)  # pylint: disable=redefined-variable-type
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
        self.name = "download-action"
        self.description = "download action"
        self.summary = "download-action"

        self.url = url
        self.key = key
        # Store the files in a sub-directory to keep the path unique
        self.path = os.path.join(path, key)
        self.size = -1

    def reader(self):
        raise LAVABug("'reader' function unimplemented")

    def cleanup(self, connection):
        if os.path.exists(self.path):
            self.logger.debug("Cleaning up download directory: %s", self.path)
            shutil.rmtree(self.path)
        self.set_namespace_data(action='download-action', label=self.key, key='file', value='')
        super(DownloadHandler, self).cleanup(connection)

    def _url_to_fname_suffix(self, path, modify):
        filename = os.path.basename(self.url.path)
        parts = filename.split('.')
        # Handle unmodified filename
        # Also files without suffixes, e.g. kernel images
        if not modify or len(parts) == 1:
            return (os.path.join(path, filename),
                    None)
        else:
            return (os.path.join(path, '.'.join(parts[:-1])),
                    parts[-1])

    @contextlib.contextmanager
    def _decompressor_stream(self):  # pylint: disable=too-many-branches
        dwnld_file = None
        compression = False
        if 'images' in self.parameters and self.key in self.parameters['images']:
            compression = self.parameters['images'][self.key].get('compression', False)
        else:
            if self.key == 'ramdisk':
                self.logger.debug("Not decompressing ramdisk as can be used compressed.")
            else:
                compression = self.parameters[self.key].get('compression', False)

        fname, _ = self._url_to_fname_suffix(self.path, compression)
        if os.path.isdir(fname):
            raise JobError("Download '%s' is a directory, not a file" % fname)
        if os.path.exists(fname):
            os.remove(fname)

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
                try:
                    buff = decompressor.decompress(buff)
                except EOFError as eof_exc:
                    # EOFError can be raised when decompressing a bz2 archive
                    # generated by pbzip2. If there is something in unsused_data
                    # try to continue decompression.
                    if compression == 'bz2' and decompressor.unused_data:
                        buff = decompressor.unused_data
                    else:
                        error_message = str(eof_exc)
                        self.logger.exception(error_message)
                        raise JobError(error_message)
                except (IOError, lzma.error, zlib.error) as exc:  # pylint: disable=no-member
                    error_message = str(exc)
                    self.logger.exception(error_message)
                    raise JobError(error_message)
            dwnld_file.write(buff)

        try:
            with open(fname, 'wb') as dwnld_file:
                yield (write, fname)
        except (IOError, OSError) as exc:
            msg = "Unable to open %s: %s" % (fname, exc.strerror)
            self.logger.error(msg)
            raise InfrastructureError(msg)

    def validate(self):
        super(DownloadHandler, self).validate()
        if 'images' in self.parameters and self.key in self.parameters['images']:
            image = self.parameters['images'][self.key]
            self.url = lavaurl.urlparse(image['url'])
            compression = image.get('compression', None)
            archive = image.get('archive', None)
            image_name, _ = self._url_to_fname_suffix(self.path, compression)
            image_arg = image.get('image_arg', None)
            overlay = image.get('overlay', False)
            self.set_namespace_data(action='download-action', label=self.key,
                                    key='file', value=image_name)
            self.set_namespace_data(action='download-action', label=self.key,
                                    key='image_arg', value=image_arg)
        else:
            self.url = lavaurl.urlparse(self.parameters[self.key]['url'])
            compression = self.parameters[self.key].get('compression', None)
            archive = self.parameters[self.key].get('archive', None)
            overlay = self.parameters.get('overlay', False)
            fname, _ = self._url_to_fname_suffix(self.path, compression)
            self.set_namespace_data(action='download-action', label=self.key, key='file', value=fname)

        if overlay:
            self.set_namespace_data(action='download-action', label=self.key, key='overlay', value=overlay)
        if compression:
            if compression not in ['gz', 'bz2', 'xz', 'zip']:
                self.errors = "Unknown 'compression' format '%s'" % compression
        if archive:
            if archive not in ['tar']:
                self.errors = "Unknown 'archive' format '%s'" % archive
        # pass kernel type to boot Action
        if self.key == 'kernel' and ('kernel' in self.parameters):
            self.set_namespace_data(
                action='download-action', label='type', key=self.key,
                value=self.parameters[self.key].get('type', None))

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        def progress_unknown_total(downloaded_sz, last_val):
            """ Compute progress when the size is unknown """
            condition = downloaded_sz >= last_val + 25 * 1024 * 1024
            return (condition, downloaded_sz,
                    "progress %dMB" % (int(downloaded_sz / (1024 * 1024))) if condition else "")

        def progress_known_total(downloaded_sz, last_val):
            """ Compute progress when the size is known """
            percent = math.floor(downloaded_sz / float(self.size) * 100)
            condition = percent >= last_val + 5
            return (condition, percent,
                    "progress %3d%% (%dMB)" % (percent, int(downloaded_sz / (1024 * 1024))) if condition else "")

        connection = super(DownloadHandler, self).run(connection, max_end_time, args)
        # self.cookies = self.job.context.config.lava_cookies  # FIXME: work out how to restore
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()

        # Create a fresh directory if the old one has been removed by a previous cleanup
        # (when retrying inside a RetryAction)
        try:
            os.makedirs(self.path, 0o755)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise InfrastructureError("Unable to create %s: %s" % (self.path, str(exc)))

        # Download the file
        with self._decompressor_stream() as (writer, fname):

            if 'images' in self.parameters and self.key in self.parameters['images']:
                remote = self.parameters['images'][self.key]
            else:
                remote = self.parameters[self.key]
            md5sum = remote.get('md5sum', None)
            sha256sum = remote.get('sha256sum', None)

            self.logger.info("downloading %s", remote['url'])
            self.logger.debug("saving as %s", fname)

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
        self.set_namespace_data(action='download-action', label=self.key, key='file', value=fname)
        self.set_namespace_data(action='download-action', label=self.key, key='md5', value=md5.hexdigest())
        self.set_namespace_data(action='download-action', label=self.key, key='sha256', value=sha256.hexdigest())

        # handle archive files
        if 'images' in self.parameters and self.key in self.parameters['images']:
            archive = self.parameters['images'][self.key].get('archive', False)
        else:
            archive = self.parameters[self.key].get('archive', None)
        if archive:
            origin = fname
            target_fname = os.path.basename(origin).rstrip('.' + archive)
            target_fname_path = os.path.join(os.path.dirname(origin),
                                             target_fname)
            if os.path.exists(target_fname_path):
                os.remove(target_fname_path)

            if archive == 'tar':
                untar_file(origin, None, member=target_fname,
                           outfile=target_fname_path)
                self.set_namespace_data(action='download-action', label=self.key, key='file', value=target_fname_path)
                self.set_namespace_data(action='download-action', label='file', key=self.key, value=target_fname)
            self.logger.debug("Using %s archive" % archive)

        if md5sum is not None:
            chk_md5sum = self.get_namespace_data(action='download-action', label=self.key, key='md5')
            if md5sum != chk_md5sum:
                self.logger.error("md5sum of downloaded content: %s" % chk_md5sum)
                self.logger.info("sha256sum of downloaded content: %s" % (
                    self.get_namespace_data(action='download-action', label=self.key, key='sha256')))
                self.results = {'fail': {
                    'md5': md5sum, 'download': chk_md5sum}}
                raise JobError("MD5 checksum for '%s' does not match." % fname)
            self.results = {'success': {'md5': md5sum}}

        if sha256sum is not None:
            chk_sha256sum = self.get_namespace_data(action='download-action', label=self.key, key='sha256')
            if sha256sum != chk_sha256sum:
                self.logger.info("md5sum of downloaded content: %s" % (
                    self.get_namespace_data(action='download-action', label=self.key, key='md5')))
                self.logger.error("sha256sum of downloaded content: %s" % chk_sha256sum)
                self.results = {'fail': {
                    'sha256': sha256sum, 'download': chk_sha256sum}}
                raise JobError("SHA256 checksum for '%s' does not match." % fname)
            self.results = {'success': {'sha256': sha256sum}}

        # certain deployments need prefixes set
        if self.parameters['to'] == 'tftp' or self.parameters['to'] == 'nbd':
            suffix = self.get_namespace_data(action='tftp-deploy', label='tftp',
                                             key='suffix')
            self.set_namespace_data(action='download-action', label='file', key=self.key,
                                    value=os.path.join(suffix, self.key, os.path.basename(fname)))
        elif self.parameters['to'] == 'iso-installer':
            suffix = self.get_namespace_data(action='deploy-iso-installer',
                                             label='iso', key='suffix')
            self.set_namespace_data(action='download-action', label='file', key=self.key,
                                    value=os.path.join(suffix, self.key, os.path.basename(fname)))
        else:
            self.set_namespace_data(action='download-action', label='file', key=self.key, value=fname)

        # xnbd protocoll needs to know the location
        nbdroot = self.get_namespace_data(action='download-action', label='file', key='nbdroot')
        if 'lava-xnbd' in self.parameters and nbdroot:
            self.parameters['lava-xnbd']['nbdroot'] = nbdroot

        self.results = {
            'label': self.key,
            'md5sum': str(self.get_namespace_data(
                action='download-action', label=self.key, key='md5')),
            'sha256sum': str(self.get_namespace_data(
                action='download-action', label=self.key, key='sha256'))
        }
        return connection


class FileDownloadAction(DownloadHandler):
    """
    Download a resource from file (copy)
    """

    def __init__(self, key, path, url):
        super(FileDownloadAction, self).__init__(key, path, url)
        self.name = "file-download"
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
            raise InfrastructureError("Unable to write to %s: %s" % (self.url.path, str(exc)))
        finally:
            if reader is not None:
                reader.close()


class HttpDownloadAction(DownloadHandler):
    """
    Download a resource over http or https using requests module
    """

    def __init__(self, key, path, url):
        super(HttpDownloadAction, self).__init__(key, path, url)
        self.name = "http-download"
        self.description = "use http to download the file"
        self.summary = "http download"

    def validate(self):
        super(HttpDownloadAction, self).validate()
        res = None
        try:
            self.logger.debug("Validating that %s exists", self.url.geturl())
            res = requests.head(self.url.geturl(), allow_redirects=True)
            if res.status_code != requests.codes.OK:  # pylint: disable=no-member
                # try using (the slower) get for services with broken redirect support
                self.logger.debug("Using GET because HEAD is not supported properly")
                res.close()
                res = requests.get(
                    self.url.geturl(), allow_redirects=True, stream=True)
                if res.status_code != requests.codes.OK:  # pylint: disable=no-member
                    self.errors = "Resources not available at '%s'" % (self.url.geturl())

            self.size = int(res.headers.get('content-length', -1))
        except requests.Timeout:
            self.logger.error("Request timed out")
            self.errors = "'%s' timed out" % (self.url.geturl())
        except requests.RequestException as exc:
            self.logger.error("Ressource not available")
            self.errors = "Unable to get '%s': %s" % (self.url.geturl(), str(exc))
        finally:
            if res is not None:
                res.close()

    def reader(self):
        res = None
        try:
            res = requests.get(self.url.geturl(), allow_redirects=True,
                               stream=True)
            if res.status_code != requests.codes.OK:  # pylint: disable=no-member
                # This is an Infrastructure error because the validate function
                # checked that the file does exist.
                raise InfrastructureError("Unable to download '%s'" % (self.url.geturl()))
            for buff in res.iter_content(HTTP_DOWNLOAD_CHUNK_SIZE):
                yield buff
        except requests.RequestException as exc:
            raise InfrastructureError("Unable to download '%s': %s" % (self.url.geturl(), str(exc)))
        finally:
            if res is not None:
                res.close()


class ScpDownloadAction(DownloadHandler):
    """
    Download a resource over scp
    """

    def __init__(self, key, path, url):
        super(ScpDownloadAction, self).__init__(key, path, url)
        self.name = "scp-download"
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
        self.name = "qcow2-convert"
        self.description = "convert qcow image using qemu-img"
        self.summary = "qcow conversion"
        self.key = key

    def run(self, connection, max_end_time, args=None):
        connection = super(QCowConversionAction, self).run(connection, max_end_time, args)
        fname = self.get_namespace_data(
            action='download-action',
            label=self.key,
            key='file'
        )
        origin = fname
        # Remove the '.qcow2' extension and add '.img'
        if fname.endswith('.qcow2'):
            fname = fname[:-6]
        fname += ".img"

        self.logger.debug("Converting downloaded image from qcow2 to raw")
        try:
            subprocess.check_output(['qemu-img', 'convert',
                                     '-f', 'qcow2',
                                     '-O', 'raw', origin, fname],
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as exc:
            self.logger.error("Unable to convert the qcow2 image")
            self.logger.error(exc.output)
            raise JobError(exc.output)

        self.set_namespace_data(action=self.name, label=self.key, key='file', value=fname)
        self.set_namespace_data(action=self.name, label='file', key=self.key, value=fname)
        return connection
