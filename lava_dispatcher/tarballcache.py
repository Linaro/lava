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

import contextlib
import errno
import fcntl
import logging
import os

import lava_dispatcher.utils as utils

from lava_dispatcher.downloader import (
    download_image,
)


def get_tarballs(context, image_url, scratch_dir, generator):
    """
    Tries to return a cached copy array of (boot_tgz, root_tgz, distro). If no cache
    exists for this image_url, then it:
     * places a global lock for the image_url to prevent other dispatchers
       from concurrently building tarballs for the same image
     * downloads the image
     * calls the generator function to build the tarballs

    generator - a callback to a function that can generate the tarballs given
    a local copy .img file
    """
    logging.info('try to find cached tarballs for %s' % image_url)
    with _cache_locked(image_url, context.config.lava_cachedir) as cachedir:
        boot_tgz = os.path.join(cachedir, 'boot.tgz')
        root_tgz = os.path.join(cachedir, 'root.tgz')
        distro_file = os.path.join(cachedir, 'distro')

        if os.path.exists(boot_tgz) and os.path.exists(root_tgz):
            distro = _get_distro(cachedir, distro_file)
            if distro is not None:
                logging.info('returning cached copies')
                (boot_tgz, root_tgz) = _link(boot_tgz, root_tgz, scratch_dir)
                return boot_tgz, root_tgz, distro
        else:
            logging.info('no cache found for %s' % image_url)

        _clear_cache(boot_tgz, root_tgz, distro_file)
        image = download_image(image_url, context, cachedir)
        (boot_tgz, root_tgz, distro) = generator(image)
        with open(distro_file, 'w') as f:
            f.write(distro)
        _link(boot_tgz, root_tgz, cachedir)
        os.unlink(image)
        return boot_tgz, root_tgz, distro


def _link(boot_tgz, root_tgz, destdir):
    dboot_tgz = os.path.join(destdir, 'boot.tgz')
    droot_tgz = os.path.join(destdir, 'root.tgz')
    os.link(boot_tgz, dboot_tgz)
    os.link(root_tgz, droot_tgz)
    return dboot_tgz, droot_tgz


def _clear_cache(boot_tgz, root_tgz, distro_file):
    logging.info('Clearing cache contents')
    if os.path.exists(boot_tgz):
        os.unlink(boot_tgz)
    if os.path.exists(root_tgz):
        os.unlink(root_tgz)
    if os.path.exists(distro_file):
        os.unlink(distro_file)


def _get_distro(cachedir, distro_file):
    try:
        with open(distro_file, 'r') as f:
            return f.read()
    except IOError:
        logging.warning('No distro found for cached tarballs in %s' % cachedir)
    return None


@contextlib.contextmanager
def _cache_locked(image_url, cachedir):
    cachedir = utils.url_to_cache(image_url, cachedir).replace('.', '-')
    try:
        os.makedirs(cachedir)
    except OSError as e:
        if e.errno != errno.EEXIST:  # directory may already exist and is okay
            raise

    lockfile = os.path.join(cachedir, 'lockfile')
    with open(lockfile, 'w') as f:
        logging.info('aquiring lock for %s' % lockfile)
        try:
            fcntl.lockf(f, fcntl.LOCK_EX)
            yield cachedir
        finally:
            fcntl.lockf(f, fcntl.LOCK_UN)
