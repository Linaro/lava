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
import shutil
import time
import hashlib
import requests
import subprocess
import bz2
import contextlib
import lzma
import zlib
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.protocols.lxc import LxcProtocol
from lava_dispatcher.actions.deploy import DeployAction
from lava_dispatcher.actions.deploy.overlay import OverlayAction
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.action import (
    Action,
    InfrastructureError,
    JobError,
    LAVABug,
    Pipeline,
)
from lava_dispatcher.logical import (
    Deployment,
    RetryAction,
)
from lava_dispatcher.utils.compression import untar_file
from lava_dispatcher.utils.filesystem import (
    copy_to_lxc,
    lava_lxc_home,
    copy_overlay_to_lxc,
)
from lava_dispatcher.utils.constants import (
    FILE_DOWNLOAD_CHUNK_SIZE,
    HTTP_DOWNLOAD_CHUNK_SIZE,
    SCP_DOWNLOAD_CHUNK_SIZE,
)
from lava_dispatcher.actions.boot.fastboot import EnterFastbootAction
from lava_dispatcher.actions.boot.u_boot import UBootEnterFastbootAction

import urllib.parse as lavaurl

# pylint: disable=logging-not-lazy

# FIXME: separate download actions for decompressed and uncompressed downloads
# so that the logic can be held in the Strategy class, not the Action.
# FIXME: create a download3.py which uses urllib.urlparse


class DownloaderAction(RetryAction):
    """
    The retry pipeline for downloads.
    To allow any deploy action to work with multinode, each call *must* set a unique path.
    """

    name = "download-retry"
    description = "download with retry"
    summary = "download-retry"

    def __init__(self, key, path, uniquify=True):
        super().__init__()
        self.max_retries = 3
        self.key = key  # the key in the parameters of what to download
        self.path = path  # where to download
        self.uniquify = uniquify

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        # Find the right action according to the url
        if 'images' in parameters and self.key in parameters['images']:
            url = parameters['images'][self.key].get('url')
        else:
            url = parameters[self.key].get('url')
        if url is None:
            raise JobError("Invalid deploy action: 'url' is missing for '%s'" % self.key)

        url = lavaurl.urlparse(url)
        if url.scheme == 'scp':
            action = ScpDownloadAction(self.key, self.path, url, self.uniquify)
        elif url.scheme == 'http' or url.scheme == 'https':
            action = HttpDownloadAction(self.key, self.path, url, self.uniquify)  # pylint: disable=redefined-variable-type
        elif url.scheme == 'file':
            action = FileDownloadAction(self.key, self.path, url, self.uniquify)  # pylint: disable=redefined-variable-type
        elif url.scheme == 'lxc':
            action = LxcDownloadAction(self.key, self.path, url)  # pylint: disable=redefined-variable-type
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

    name = "download-action"
    description = "download action"
    summary = "download-action"

    def __init__(self, key, path, url, uniquify=True):
        super().__init__()
        self.url = url
        self.key = key
        # If uniquify is True, store the files in a sub-directory to keep the
        # path unique.
        self.path = os.path.join(path, key) if uniquify else path
        self.size = -1

    def reader(self):
        raise LAVABug("'reader' function unimplemented")

    def cleanup(self, connection):
        if os.path.exists(self.path):
            self.logger.debug("Cleaning up download directory: %s", self.path)
            shutil.rmtree(self.path)
        self.set_namespace_data(action='download-action', label=self.key, key='file', value='')
        super().cleanup(connection)

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

    def validate(self):
        super().validate()
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
            self.set_namespace_data(action='download-action', label=self.key,
                                    key='compression', value=compression)
        else:
            self.url = lavaurl.urlparse(self.parameters[self.key]['url'])
            compression = self.parameters[self.key].get('compression', None)
            archive = self.parameters[self.key].get('archive', None)
            overlay = self.parameters.get('overlay', False)
            fname, _ = self._url_to_fname_suffix(self.path, compression)
            self.set_namespace_data(action='download-action', label=self.key, key='file', value=fname)
            self.set_namespace_data(action='download-action', label=self.key, key='compression', value=compression)

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

        connection = super().run(connection, max_end_time, args)
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

        if 'images' in self.parameters and self.key in self.parameters['images']:
            remote = self.parameters['images'][self.key]
            compression = self.parameters['images'][self.key].get(
                'compression', False)

        else:
            remote = self.parameters[self.key]
            if self.key == 'ramdisk':
                compression = False
                self.logger.debug(
                    "Not decompressing ramdisk as can be used compressed.")
            else:
                compression = self.parameters[self.key].get('compression',
                                                            False)

        md5sum = remote.get('md5sum', None)
        sha256sum = remote.get('sha256sum', None)

        fname, _ = self._url_to_fname_suffix(self.path, compression)
        if os.path.isdir(fname):
            raise JobError("Download '%s' is a directory, not a file" % fname)
        if os.path.exists(fname):
            os.remove(fname)

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

        decompress_command = None
        if compression:
            if compression == 'gz':
                decompress_command = 'gunzip'
            elif compression == 'bz2':
                decompress_command = 'bunzip2'
            elif compression == 'xz':
                decompress_command = 'unxz'
            self.logger.debug("Using %s decompression" % compression)
        else:
            self.logger.debug("No compression specified.")

        def update_progress():
            nonlocal downloaded_size, last_value, md5, sha256
            downloaded_size += len(buff)
            (printing, new_value, msg) = progress(downloaded_size,
                                                  last_value)
            if printing:
                last_value = new_value
                self.logger.debug(msg)
            md5.update(buff)
            sha256.update(buff)

        if compression and decompress_command:
            try:
                with open(fname, 'wb') as dwnld_file:
                    proc = subprocess.Popen([decompress_command],
                                            stdin=subprocess.PIPE,
                                            stdout=dwnld_file)
            except (IOError, OSError) as exc:
                msg = "Unable to open %s: %s" % (fname, exc.strerror)
                self.logger.error(msg)
                raise InfrastructureError(msg)

            with proc.stdin as pipe:
                for buff in self.reader():
                    update_progress()
                    try:
                        pipe.write(buff)
                    except BrokenPipeError as exc:
                        error_message = str(exc)
                        self.logger.exception(error_message)
                        msg = "Make sure the 'compression' is corresponding " \
                              "to the image file type."
                        self.logger.error(msg)
                        raise JobError(error_message)
            proc.wait()
        else:
            with open(fname, 'wb') as dwnld_file:
                for buff in self.reader():
                    update_progress()
                    dwnld_file.write(buff)

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
            'size': downloaded_size,
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

    name = "file-download"
    description = "copy a local file"
    summary = "local file copy"

    def validate(self):
        super().validate()
        try:
            self.logger.debug("Validating that %s exists", self.url.geturl())
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

    name = "http-download"
    description = "use http to download the file"
    summary = "http download"

    def validate(self):
        super().validate()
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
                    self.errors = "Resource unavailable at '%s' (%d)" % (self.url.geturl(), res.status_code)

            self.size = int(res.headers.get('content-length', -1))
        except requests.Timeout:
            self.logger.error("Request timed out")
            self.errors = "'%s' timed out" % (self.url.geturl())
        except requests.RequestException as exc:
            self.logger.error("Resource not available")
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

    name = "scp-download"
    description = "Use scp to copy the file"
    summary = "scp download"

    def validate(self):
        super().validate()
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


class LxcDownloadAction(Action):
    """
    Map an already downloaded resource to the correct path.
    """

    name = "lxc-download"
    description = "Map to the correct lxc path"
    summary = "lxc download"

    def __init__(self, key, path, url):
        super().__init__()
        self.key = key
        self.path = path
        self.url = url

    def validate(self):
        super().validate()
        if self.url.scheme != 'lxc':
            self.errors = "lxc:/// url scheme is invalid"
        if not self.url.path:
            self.errors = "Invalid path in lxc:/// url"

    def run(self, connection, max_end_time, args=None):
        connection = super().run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError("Erroneous lxc url '%s' without protocol %s" %
                           self.url, LxcProtocol.name)

        fname = os.path.basename(self.url.path)
        lxc_home = lava_lxc_home(lxc_name, self.job.parameters['dispatcher'])
        file_path = os.path.join(lxc_home, fname)
        self.logger.debug("Found '%s' matching '%s'", file_path, fname)
        if os.path.exists(file_path):
            self.set_namespace_data(action='download-action', label=self.key,
                                    key='file', value=file_path)
        else:
            raise JobError("Resource unavailable: %s" % self.url.path)
        return connection


class QCowConversionAction(Action):
    """
    explicit action for qcow conversion to avoid reliance
    on filename suffix
    """

    name = "qcow2-convert"
    description = "convert qcow image using qemu-img"
    summary = "qcow conversion"

    def __init__(self, key):
        super().__init__()
        self.key = key

    def run(self, connection, max_end_time, args=None):
        connection = super().run(connection, max_end_time, args)
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


class Download(Deployment):
    """
    Strategy class for a download deployment.
    Downloads the relevant parts, copies to LXC if available.
    """
    compatibility = 1
    name = 'download'

    def __init__(self, parent, parameters):
        super().__init__(parent)
        self.action = DownloadAction()
        self.action.section = self.action_type
        self.action.job = self.job
        parent.add_action(self.action, parameters)

    @classmethod
    def accepts(cls, device, parameters):
        if 'to' not in parameters:
            return False, '"to" is not in deploy parameters'
        if parameters['to'] != 'download':
            return False, '"to" parameter is not "download"'
        return True, 'accepted'


class DownloadAction(DeployAction):  # pylint:disable=too-many-instance-attributes

    name = "download-deploy"
    description = "download files and copy to LXC if available"
    summary = "download deployment"

    def __init__(self):
        super().__init__()
        self.download_dir = None

    def validate(self):
        super().validate()
        self.set_namespace_data(action=self.name, label='download-dir',
                                key='dir', value=self.download_dir)

    def populate(self, parameters):
        self.internal_pipeline = Pipeline(parent=self, job=self.job,
                                          parameters=parameters)
        # Check if the device has a power command such as HiKey, Dragonboard,
        # etc. against device that doesn't like Nexus, etc.
        # This is required in order to power on the device so that when the
        # test job writer wants to perform some operation using a
        # lava-test-shell action that follows, this becomes mandatory. Think of
        # issuing any fastboot commands on the powered on device.
        #
        # NOTE: Add more power on strategies, if required for specific devices.
        if self.job.device.get('fastboot_via_uboot', False):
            self.internal_pipeline.add_action(ConnectDevice())
            self.internal_pipeline.add_action(UBootEnterFastbootAction())
        elif self.job.device.hard_reset_command:
            self.force_prompt = True
            self.internal_pipeline.add_action(ConnectDevice())
            self.internal_pipeline.add_action(ResetDevice())
        else:
            self.internal_pipeline.add_action(EnterFastbootAction())

        self.download_dir = self.mkdtemp()
        image_keys = sorted(parameters['images'].keys())
        for image in image_keys:
            if image != 'yaml_line':
                self.internal_pipeline.add_action(DownloaderAction(
                    image, self.download_dir))
        if self.test_needs_overlay(parameters):
            self.internal_pipeline.add_action(OverlayAction())
        self.internal_pipeline.add_action(CopyToLxcAction())


class CopyToLxcAction(DeployAction):
    """
    Copy downloaded files to LXC within LAVA_LXC_HOME.
    """

    name = "copy-to-lxc"
    description = "copy files to lxc"
    summary = "copy to lxc"

    def __init__(self):
        super().__init__()
        self.retries = 3
        self.sleep = 10

    def run(self, connection, max_end_time, args=None):  # pylint: disable=too-many-locals
        connection = super().run(connection, max_end_time, args)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [protocol for protocol in self.job.protocols if protocol.name == LxcProtocol.name][0]
        if protocol:
            lxc_name = protocol.lxc_name
        else:
            return connection

        # Copy each file to LXC.
        namespace = self.parameters['namespace']
        images = self.data[namespace]['download-action'].keys()
        for image in images:
            src = self.get_namespace_data(action='download-action',
                                          label=image, key='file')
            # The archive extraction logic and some deploy logic in
            # DownloadHandler will set a label 'file' in the namespace but
            # that file would have been dealt with and the actual path may not
            # exist, though the key exists as part of the namespace, which we
            # can ignore safely, hence we continue on invalid src.
            if not src:
                continue
            copy_to_lxc(lxc_name, src, self.job.parameters['dispatcher'])
        overlay_file = self.get_namespace_data(action='compress-overlay',
                                               label='output', key='file')
        if overlay_file is None:
            self.logger.debug("skipped %s", self.name)
        else:
            copy_overlay_to_lxc(lxc_name, overlay_file,
                                self.job.parameters['dispatcher'], namespace)
        return connection
