# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#         Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import contextlib
import hashlib
import math
import os
import pathlib
import subprocess  # nosec - verified.
import time
from typing import TYPE_CHECKING
from urllib.parse import quote_plus, urlparse

import requests

from lava_common.constants import (
    FILE_DOWNLOAD_CHUNK_SIZE,
    HTTP_DOWNLOAD_CHUNK_SIZE,
    HTTP_DOWNLOAD_TIMEOUT,
    SCP_DOWNLOAD_CHUNK_SIZE,
)
from lava_common.exceptions import InfrastructureError, JobError, LAVABug
from lava_dispatcher.action import Action, Pipeline
from lava_dispatcher.actions.boot.fastboot import EnterFastbootAction
from lava_dispatcher.actions.boot.u_boot import UBootEnterFastbootAction
from lava_dispatcher.actions.deploy.apply_overlay import AppendOverlays
from lava_dispatcher.actions.deploy.overlay import CreateOverlay, OverlayAction
from lava_dispatcher.connections.serial import ConnectDevice
from lava_dispatcher.logical import RetryAction
from lava_dispatcher.power import ResetDevice
from lava_dispatcher.protocols.lxc import LxcProtocol
from lava_dispatcher.utils.compression import untar_file
from lava_dispatcher.utils.filesystem import (
    copy_overlay_to_lxc,
    copy_to_lxc,
    lava_lxc_home,
)
from lava_dispatcher.utils.network import requests_retry
from lava_dispatcher.utils.strings import substitute_address_with_static_info

if TYPE_CHECKING:
    from lava_dispatcher.job import Job


class DownloaderAction(RetryAction):
    """
    The retry pipeline for downloads.
    To allow any deploy action to work with multinode, each call *must* set a unique path.
    """

    name = "download-retry"
    description = "download with retry"
    summary = "download-retry"

    def __init__(self, job: Job, key, path, params, uniquify=True):
        super().__init__(job)
        self.max_retries = 3
        self.key = key  # the key in the parameters of what to download
        self.path = path  # where to download
        self.uniquify = uniquify
        self.params = params

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)

        # Find the right action according to the url
        url = self.params.get("url")
        if url is None:
            raise JobError(
                "Invalid deploy action: 'url' is missing for '%s'" % self.key
            )

        url = urlparse(url)
        if url.scheme == "scp":
            action = ScpDownloadAction(
                self.job, self.key, self.path, url, self.uniquify, params=self.params
            )
        elif url.scheme in ["http", "https"]:
            action = HttpDownloadAction(
                self.job, self.key, self.path, url, self.uniquify, params=self.params
            )
        elif url.scheme == "file":
            action = FileDownloadAction(
                self.job, self.key, self.path, url, self.uniquify, params=self.params
            )
        elif url.scheme == "lxc":
            action = LxcDownloadAction(self.job, self.key, self.path, url)
        elif url.scheme == "downloads":
            action = PreDownloadedAction(
                self.job, self.key, url, self.path, self.uniquify, params=self.params
            )
        else:
            raise JobError("Unsupported url protocol scheme: %s" % url.scheme)
        self.pipeline.add_action(action)
        overlays = self.params.get("overlays", [])
        for overlay in overlays:
            if overlay == "lava":
                # Special case, don't download an overlay,
                # just defined where to find overlays
                continue
            self.pipeline.add_action(
                DownloaderAction(
                    self.job,
                    "%s.%s" % (self.key, overlay),
                    self.path,
                    params=overlays[overlay],
                )
            )
        if overlays:
            if "lava" in overlays and not self.test_needs_overlay(self.parameters):
                self.pipeline.add_action(CreateOverlay(self.job))
            self.pipeline.add_action(
                AppendOverlays(self.job, self.key, params=self.params)
            )


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

    name = "download-action"
    description = "download action"
    summary = "download-action"
    timeout_exception = InfrastructureError

    # Supported decompression commands
    decompress_command_map = {
        "bz2": "bunzip2",
        "gz": "gunzip",
        "xz": "unxz",
        "zstd": "unzstd",
    }

    def __init__(self, job: Job, key, path, url, uniquify=True, params=None):
        super().__init__(job)
        self.url = url
        self.key = key
        self.size = -1

        self.path = path
        # Store the files in a sub-directory to keep the path unique.
        if uniquify:
            self.path = os.path.join(path, key)
        self.fname = None
        self.params = params

    def reader(self):
        raise LAVABug("'reader' function unimplemented")

    def cleanup(self, connection):
        if self.fname is not None and os.path.exists(self.fname):
            self.logger.debug("Cleaning up downloaded image: %s", self.fname)
            try:
                os.remove(self.fname)
                self.set_namespace_data(
                    action="download-action", label=self.key, key="file", value=""
                )
            except OSError as exc:
                self.logger.debug(str(exc))
        super().cleanup(connection)

    def _compression(self):
        if self.key == "ramdisk":
            return False
        return self.params.get("compression", False)

    def _url_to_fname(self):
        compression = self._compression()
        filename = os.path.basename(self.url.path)

        # Don't rename files we don't decompress during download
        if not compression or (compression not in self.decompress_command_map):
            return os.path.join(self.path, filename)

        parts = filename.split(".")
        # Files without suffixes, e.g. kernel images
        if len(parts) == 1:
            return os.path.join(self.path, filename)
        return os.path.join(self.path, ".".join(parts[:-1]))

    def validate(self):
        super().validate()
        # Check that self.key is not a path
        if len(pathlib.Path(self.key).parts) != 1:
            raise JobError("Invalid key %r" % self.key)

        self.params["url"] = substitute_address_with_static_info(
            self.params["url"], self.job.device.get("static_info", [])
        )

        self.url = urlparse(self.params["url"])
        compression = self.params.get("compression")
        archive = self.params.get("archive")
        overlay = self.params.get("overlay", False)
        image_arg = self.params.get("image_arg")

        self.fname = self._url_to_fname()
        if self.fname.endswith("/"):
            raise JobError("Cannot download a directory for %s" % self.key)
        # Save into the namespaced data
        self.set_namespace_data(
            action="download-action", label=self.key, key="file", value=self.fname
        )
        self.set_namespace_data(
            action="download-action",
            label=self.key,
            key="compression",
            value=compression,
        )
        if image_arg is not None:
            self.set_namespace_data(
                action="download-action",
                label=self.key,
                key="image_arg",
                value=image_arg,
            )
        if overlay:
            self.set_namespace_data(
                action="download-action", label=self.key, key="overlay", value=overlay
            )

        if compression and compression not in ["gz", "bz2", "xz", "zip", "zstd"]:
            self.errors = "Unknown 'compression' format '%s'" % compression
        if archive and archive not in ["tar"]:
            self.errors = "Unknown 'archive' format '%s'" % archive
        # pass kernel type to boot Action
        if self.key == "kernel" and ("kernel" in self.parameters):
            self.set_namespace_data(
                action="download-action",
                label="type",
                key=self.key,
                value=self.parameters[self.key].get("type"),
            )

    def _check_checksum(self, algorithm, actual, expected):
        if expected is None:
            return
        if actual == expected:
            self.results = {"success": {algorithm: actual}}
            return

        self.logger.error(
            "%s sum for '%s' does not match", algorithm, self.url.geturl()
        )
        self.logger.info("actual  : %s", actual)
        self.logger.info("expected: %s", expected)

        self.results = {"fail": {algorithm: expected, "download": actual}}
        raise JobError("%s for '%s' does not match." % (algorithm, self.url.geturl()))

    def run(self, connection, max_end_time):
        def progress_unknown_total(downloaded_sz, last_val, last_update):
            """Compute progress when the size is unknown"""
            condition = (
                downloaded_sz >= last_val + 25 * 1024 * 1024
                and time.monotonic() - last_update >= 0.1
                or time.monotonic() - last_update >= 1
            )
            return (
                condition,
                downloaded_sz,
                "progress %d MB" % (int(downloaded_sz / (1024 * 1024)))
                if condition
                else "",
            )

        def progress_known_total(downloaded_sz, last_val, last_update):
            """Compute progress when the size is known"""
            percent = math.floor(downloaded_sz / float(self.size) * 100)
            condition = (
                percent >= last_val + 5 and time.monotonic() - last_update >= 0.1
            )
            return (
                condition,
                percent,
                "progress %3d %% (%d MB)"
                % (percent, int(downloaded_sz / (1024 * 1024)))
                if condition
                else "",
            )

        connection = super().run(connection, max_end_time)
        # self.cookies = self.job.context.config.lava_cookies  # FIXME: work out how to restore

        # Create a fresh directory if the old one has been removed by a previous cleanup
        # (when retrying inside a RetryAction)
        try:
            os.makedirs(self.path, 0o755, exist_ok=True)
        except OSError as exc:
            raise InfrastructureError(f"Unable to create {self.path}: {exc}")

        compression = self._compression()
        if self.key == "ramdisk":
            self.logger.debug("Not decompressing ramdisk as can be used compressed.")

        self.set_namespace_data(
            action="download-action",
            label=self.key,
            key="decompressed",
            value=bool(compression),
        )

        md5sum = self.params.get("md5sum")
        sha256sum = self.params.get("sha256sum")
        sha512sum = self.params.get("sha512sum")

        sha256 = hashlib.sha256()
        md5 = hashlib.md5() if md5sum is not None else None
        sha512 = hashlib.sha512() if sha512sum is not None else None
        hash_constructors = tuple(h for h in (md5, sha256, sha512) if h is not None)

        if os.path.isdir(self.fname):
            raise JobError("Download '%s' is a directory, not a file" % self.fname)
        if os.path.exists(self.fname):
            os.remove(self.fname)

        self.logger.info("downloading %s", self.params["url"])
        self.logger.debug("saving as %s", self.fname)

        downloaded_size = 0
        beginning = time.monotonic()
        # Choose the progress bar (is the size known?)
        if self.size <= 0:
            self.logger.debug("total size: unknown")
            last_value = -25 * 1024 * 1024
            progress = progress_unknown_total
        else:
            self.logger.debug(
                "total size: %d (%d MB)", self.size, int(self.size / (1024 * 1024))
            )
            last_value = -5
            progress = progress_known_total

        decompress_command = None
        if compression:
            if compression in self.decompress_command_map:
                decompress_command = self.decompress_command_map[compression]
                self.logger.info(
                    "Using %s to decompress %s", decompress_command, compression
                )
            else:
                self.logger.info(
                    "Compression %s specified but not decompressing during download",
                    compression,
                )
        elif not self.params.get("compression", False):
            self.logger.debug("No compression specified")

        last_update = time.monotonic()  # time for rate limiting the progress output

        def update_progress(buff):
            nonlocal downloaded_size, last_update, last_value, md5, sha256, sha512
            downloaded_size += len(buff)
            (printing, new_value, msg) = progress(
                downloaded_size, last_value, last_update
            )
            if printing:
                last_update = time.monotonic()
                last_value = new_value
                self.logger.debug(msg)

            for hash_constructor in hash_constructors:
                hash_constructor.update(buff)

        if compression and decompress_command:
            try:
                with open(self.fname, "wb") as dwnld_file:
                    self.run_download_decompression_subprocess(
                        dwnld_file, update_progress, decompress_command
                    )
            except OSError as exc:
                msg = f"Unable to open {self.fname}: {exc.strerror}"
                self.logger.error(msg)
                raise InfrastructureError(msg)
        else:
            with open(self.fname, "wb") as dwnld_file:
                for buff in self.reader():
                    update_progress(buff)
                    dwnld_file.write(buff)

        # Log the download speed
        ending = time.monotonic()
        self.logger.info(
            "%d MB downloaded in %0.2f s (%0.2f MB/s)",
            downloaded_size / (1024 * 1024),
            round(ending - beginning, 2),
            round(downloaded_size / (1024 * 1024 * (ending - beginning)), 2),
        )

        # If the remote server uses "Content-Encoding: gzip", this calculation will be wrong
        # because requests will decompress the file on the fly, creating a larger file than
        # LAVA expects.
        if self.size > 0 and self.size != downloaded_size:
            raise InfrastructureError(
                "Download finished (%i bytes) but was not expected size (%i bytes), check your networking."
                % (downloaded_size, self.size)
            )

        # set the dynamic data into the context
        self.set_namespace_data(
            action="download-action", label=self.key, key="file", value=self.fname
        )
        self.set_namespace_data(
            action="download-action", label="file", key=self.key, value=self.fname
        )
        self.set_namespace_data(
            action="download-action",
            label=self.key,
            key="sha256",
            value=sha256.hexdigest(),
        )

        # handle archive files
        archive = self.params.get("archive")
        if archive:
            if archive != "tar":
                raise JobError("Unknown archive format %r" % archive)

            target_fname_path = os.path.join(os.path.dirname(self.fname), self.key)
            self.logger.debug("Extracting %s archive in %s", archive, target_fname_path)
            untar_file(self.fname, target_fname_path)
            self.set_namespace_data(
                action="download-action",
                label=self.key,
                key="file",
                value=target_fname_path,
            )
            self.set_namespace_data(
                action="download-action",
                label="file",
                key=self.key,
                value=target_fname_path,
            )

        if md5sum is not None:
            self._check_checksum("md5", md5.hexdigest(), md5sum)
        if sha256sum is not None:
            self._check_checksum("sha256", sha256.hexdigest(), sha256sum)
        if sha512sum is not None:
            self._check_checksum("sha512", sha512.hexdigest(), sha512sum)

        # certain deployments need prefixes set
        if self.parameters.get("to"):
            if self.parameters["to"] == "tftp" or self.parameters["to"] == "nbd":
                suffix = self.get_namespace_data(
                    action="tftp-deploy", label="tftp", key="suffix"
                )
                self.set_namespace_data(
                    action="download-action",
                    label="file",
                    key=self.key,
                    value=os.path.join(suffix, self.key, os.path.basename(self.fname)),
                )
            elif self.parameters["to"] == "iso-installer":
                suffix = self.get_namespace_data(
                    action="deploy-iso-installer", label="iso", key="suffix"
                )
                self.set_namespace_data(
                    action="download-action",
                    label="file",
                    key=self.key,
                    value=os.path.join(suffix, self.key, os.path.basename(self.fname)),
                )

        # xnbd protocol needs to know the location
        nbdroot = self.get_namespace_data(
            action="download-action", label="file", key="nbdroot"
        )
        if "lava-xnbd" in self.parameters and nbdroot:
            self.parameters["lava-xnbd"]["nbdroot"] = nbdroot

        self.results = {
            "label": self.key,
            "size": downloaded_size,
            "sha256sum": str(
                self.get_namespace_data(
                    action="download-action", label=self.key, key="sha256"
                )
            ),
        }
        return connection

    def run_download_decompression_subprocess(
        self, dwnld_file, update_progress, decompress_command
    ) -> None:
        with subprocess.Popen(
            [decompress_command],
            stdin=subprocess.PIPE,
            stdout=dwnld_file,
            stderr=subprocess.PIPE,
        ) as proc:
            for buff in self.reader():
                update_progress(buff)
                try:
                    proc.stdin.write(buff)
                except BrokenPipeError as exc:
                    error_message = (
                        str(exc) + ": " + proc.stderr.read().decode("utf-8").strip()
                    )
                    self.logger.exception(error_message)
                    msg = (
                        "Make sure the 'compression' is corresponding "
                        "to the image file type."
                    )
                    self.logger.error(msg)
                    raise JobError(error_message)

            proc.stdin.close()
            compression_exitcode = proc.wait()
            if compression_exitcode != 0:
                exit_error_msg = (
                    "Decompression subprocess exited with non-zero code: "
                    + proc.stderr.read().decode("utf-8").strip()
                )
                self.logger.error(exit_error_msg)
                raise JobError(exit_error_msg)


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
            self.errors = "Image file '%s' does not exist or is not readable" % (
                self.url.path
            )

    def reader(self):
        try:
            with open(self.url.path, "rb") as reader:
                buff = reader.read(FILE_DOWNLOAD_CHUNK_SIZE)
                while buff:
                    yield buff
                    buff = reader.read(FILE_DOWNLOAD_CHUNK_SIZE)
        except OSError as exc:
            raise InfrastructureError(
                "Unable to read from %s: %s" % (self.url.path, str(exc))
            )


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
            http_cache = self.job.parameters["dispatcher"].get(
                "http_url_format_string", ""
            )

            use_cache = True
            if self.params:
                use_cache = self.params.get("use_cache", True)

            if http_cache and use_cache:
                self.logger.info("Using caching service: '%s'", http_cache)
                try:
                    self.url = urlparse(http_cache % quote_plus(self.url.geturl()))
                except TypeError as exc:
                    self.logger.error("Invalid http_url_format_string: '%s'", exc)
                    self.errors = "Invalid http_url_format_string: '%s'" % str(exc)
                    return

            headers = {"Accept-Encoding": ""}
            if self.params and "headers" in self.params:
                headers.update(self.params["headers"])
            self.logger.debug("Validating that %s exists", self.url.geturl())
            # Force the non-use of Accept-Encoding: gzip, this will permit to know the final size
            res = requests_retry(retries=9).head(
                self.url.geturl(),
                allow_redirects=True,
                headers=headers,
                timeout=HTTP_DOWNLOAD_TIMEOUT,
            )
            if res.status_code != requests.codes.OK:
                # try using (the slower) get for services with broken redirect support
                self.logger.debug("Using GET because HEAD is not supported properly")
                res.close()
                # Like for HEAD, we need get a size, so disable gzip
                res = requests_retry(retries=9).get(
                    self.url.geturl(),
                    allow_redirects=True,
                    stream=True,
                    headers=headers,
                    timeout=HTTP_DOWNLOAD_TIMEOUT,
                )
                if res.status_code != requests.codes.OK:
                    self.errors = "Resource unavailable at '%s' (%d)" % (
                        self.url.geturl(),
                        res.status_code,
                    )
                    return

            self.size = int(res.headers.get("content-length", -1))
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
            # FIXME: When requests 3.0 is released, use the enforce_content_length
            # parameter to raise an exception the file is not fully downloaded
            headers = None
            if self.params and "headers" in self.params:
                headers = self.params["headers"]
            res = requests_retry().get(
                self.url.geturl(),
                allow_redirects=True,
                stream=True,
                headers=headers,
                timeout=HTTP_DOWNLOAD_TIMEOUT,
            )
            if res.status_code != requests.codes.OK:
                # This is an Infrastructure error because the validate function
                # checked that the file does exist.
                raise InfrastructureError(
                    "Unable to download '%s'" % (self.url.geturl())
                )
            yield from res.iter_content(HTTP_DOWNLOAD_CHUNK_SIZE)
        except requests.RequestException as exc:
            raise InfrastructureError(
                "Unable to download '%s': %s" % (self.url.geturl(), str(exc))
            )
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
            size = subprocess.check_output(  # nosec - internal.
                ["ssh", self.url.netloc, "stat", "-c", "%s", self.url.path],
                stderr=subprocess.STDOUT,
            )
            self.size = int(size)
        except subprocess.CalledProcessError as exc:
            self.errors = str(exc)

    def reader(self):
        process = None
        try:
            process = subprocess.Popen(  # nosec - internal.
                ["ssh", self.url.netloc, "cat", self.url.path], stdout=subprocess.PIPE
            )
            buff = process.stdout.read(SCP_DOWNLOAD_CHUNK_SIZE)
            while buff:
                yield buff
                buff = process.stdout.read(SCP_DOWNLOAD_CHUNK_SIZE)
            if process.wait() != 0:
                raise JobError(
                    "Downloading '%s' failed with message '%s'"
                    % (self.url.geturl(), process.stderr.read())
                )
        finally:
            if process is not None:
                with contextlib.suppress(OSError):
                    process.kill()


class LxcDownloadAction(Action):
    """
    Map an already downloaded resource to the correct path.
    """

    name = "lxc-download"
    description = "Map to the correct lxc path"
    summary = "lxc download"

    def __init__(self, job: Job, key, path, url):
        super().__init__(job)
        self.key = key
        self.path = path
        self.url = url

    def validate(self):
        super().validate()
        if self.url.scheme != "lxc":
            self.errors = "lxc:/// url scheme is invalid"
        if not self.url.path:
            self.errors = "Invalid path in lxc:/// url"

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocol = [
            protocol
            for protocol in self.job.protocols
            if protocol.name == LxcProtocol.name
        ][0]
        if protocol:
            lxc_name = protocol.lxc_name
        if not lxc_name:
            raise JobError(
                "Erroneous lxc url '%s' without protocol %s" % self.url,
                LxcProtocol.name,
            )

        fname = os.path.basename(self.url.path)
        lxc_home = lava_lxc_home(lxc_name, self.job.parameters["dispatcher"])
        file_path = os.path.join(lxc_home, fname)
        self.logger.debug("Trying '%s' matching '%s'", file_path, fname)
        if os.path.exists(file_path):
            self.set_namespace_data(
                action="download-action", label=self.key, key="file", value=file_path
            )
        else:
            raise JobError("Resource unavailable: %s" % self.url.path)
        return connection


class PreDownloadedAction(Action):
    """
    Maps references to files in downloads:// to their full path.
    """

    name = "pre-downloaded"
    description = "Map to the correct downloaded path"
    summary = "pre downloaded"

    def __init__(self, job: Job, key, url, path, uniquify=True, params=None):
        super().__init__(job)
        self.key = key
        self.url = url
        self.path = path
        if uniquify:
            self.path = os.path.join(path, key)
        self.params = params

    def validate(self):
        super().validate()
        if self.url.scheme != "downloads":
            self.errors = "downloads:// url scheme is invalid"
        if not self.url.path and not self.url.netloc:
            self.errors = "Invalid path in downloads:// url"

        image_arg = self.params.get("image_arg")
        if image_arg is not None:
            self.set_namespace_data(
                action="download-action",
                label=self.key,
                key="image_arg",
                value=image_arg,
            )

    def run(self, connection, max_end_time):
        # In downloads://foo/bar.ext, "foo" is the "netloc", "/bar.ext" is
        # the path. But in downloads://foo.ext, "foo.ext" is the netloc, and
        # the path is empty.
        # In downloads:///foo/bar.ext, netloc is None while path is /foo/bar.ext.
        filename = self.url.netloc if self.url.netloc else ""
        if self.url.path:
            filename += self.url.path

        namespace = self.parameters["namespace"]
        top = pathlib.Path(self.job.tmp_dir) / "downloads" / namespace
        src = top / filename
        if not src.exists():
            existing = [
                str(f).replace(str(top) + "/", "")
                for f in top.rglob("*")
                if not f.is_dir()
            ]
            if existing:
                available = "available: " + ", ".join(existing)
            else:
                available = "not files at all available"
            raise JobError(f"Resource unavailable: {filename} ({available})")

        dest = pathlib.Path(self.path) / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Linking %s -> %s", src, dest)
        try:
            os.link(src, dest)
        except FileExistsError:
            self.logger.warning("-> destination already exists, skipping")

        self.set_namespace_data(
            action="download-action", label=self.key, key="file", value=str(dest)
        )
        self.set_namespace_data(
            action="download-action", label="file", key=self.key, value=str(dest)
        )
        if self.parameters["to"] == "tftp" or self.parameters["to"] == "nbd":
            suffix = self.get_namespace_data(
                action="tftp-deploy", label="tftp", key="suffix"
            )
            self.set_namespace_data(
                action="download-action",
                label="file",
                key=self.key,
                value=os.path.join(suffix, dest.name),
            )

        if "lava-xnbd" in self.parameters and str(self.key) == "nbdroot":
            self.parameters["lava-xnbd"]["nbdroot"] = str(dest)

        return connection


class DownloadAction(Action):
    name = "download-deploy"
    description = "download files and copy to LXC if available"
    summary = "download deployment"

    def __init__(self, job: Job):
        super().__init__(job)
        self.download_dir = None

    def validate(self):
        super().validate()
        self.set_namespace_data(
            action=self.name, label="download-dir", key="dir", value=self.download_dir
        )

    def populate(self, parameters):
        self.pipeline = Pipeline(parent=self, job=self.job, parameters=parameters)
        # Check if the device has a power command such as HiKey, Dragonboard,
        # etc. against device that doesn't like Nexus, etc.
        # This is required in order to power on the device so that when the
        # test job writer wants to perform some operation using a
        # lava-test-shell action that follows, this becomes mandatory. Think of
        # issuing any fastboot commands on the powered on device.
        #
        # NOTE: Add more power on strategies, if required for specific devices.
        if self.job.device.get("fastboot_via_uboot", False):
            self.pipeline.add_action(ConnectDevice(self.job))
            self.pipeline.add_action(UBootEnterFastbootAction(self.job))
        elif self.job.device.hard_reset_command:
            self.force_prompt = True
            self.pipeline.add_action(ConnectDevice(self.job))
            self.pipeline.add_action(ResetDevice(self.job))
        else:
            self.pipeline.add_action(EnterFastbootAction(self.job))

        self.download_dir = self.mkdtemp()
        for image_key, image_params in parameters["images"].items():
            self.pipeline.add_action(
                DownloaderAction(
                    self.job, image_key, self.download_dir, params=image_params
                )
            )
        if self.test_needs_overlay(parameters):
            self.pipeline.add_action(OverlayAction(self.job))
        self.pipeline.add_action(CopyToLxcAction(self.job))


class CopyToLxcAction(Action):
    """
    Copy downloaded files to LXC within LAVA_LXC_HOME.
    """

    name = "copy-to-lxc"
    description = "copy files to lxc"
    summary = "copy to lxc"

    def __init__(self, job: Job):
        super().__init__(job)
        self.retries = 3
        self.sleep = 10

    def run(self, connection, max_end_time):
        connection = super().run(connection, max_end_time)
        # this is the device namespace - the lxc namespace is not accessible
        lxc_name = None
        protocols = [
            protocol
            for protocol in self.job.protocols
            if protocol.name == LxcProtocol.name
        ]
        if protocols:
            lxc_name = protocols[0].lxc_name
        else:
            return connection

        # Copy each file to LXC.
        for image in self.get_namespace_keys("download-action"):
            src = self.get_namespace_data(
                action="download-action", label=image, key="file"
            )
            # The archive extraction logic and some deploy logic in
            # DownloadHandler will set a label 'file' in the namespace but
            # that file would have been dealt with and the actual path may not
            # exist, though the key exists as part of the namespace, which we
            # can ignore safely, hence we continue on invalid src.
            if not src:
                continue
            copy_to_lxc(lxc_name, src, self.job.parameters["dispatcher"])
        overlay_file = self.get_namespace_data(
            action="compress-overlay", label="output", key="file"
        )
        if overlay_file is None:
            self.logger.debug("skipped %s", self.name)
        else:
            copy_overlay_to_lxc(
                lxc_name,
                overlay_file,
                self.job.parameters["dispatcher"],
                self.parameters["namespace"],
            )
        return connection
