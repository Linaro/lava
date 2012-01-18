# Copyright (C) 2011 Linaro Limited
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

import errno
import logging
import os
import shutil
import urllib2
import urlparse
from shlex import shlex

def download(url, path="", verbose_failure=1):
    urlpath = urlparse.urlsplit(url).path
    filename = os.path.basename(urlpath)
    if path:
        filename = os.path.join(path,filename)
    fd = open(filename, "w")
    try:
        response = urllib2.urlopen(urllib2.quote(url, safe=":/"), timeout=30)
        fd = open(filename, 'wb')
        shutil.copyfileobj(response,fd,0x10000)
        fd.close()
        response.close()
    except:
        if verbose_failure:
            logging.exception("download failed")
        raise RuntimeError("Could not retrieve %s" % url)
    return filename

def download_with_cache(url, path="", cachedir=""):
    cache_loc = url_to_cache(url, cachedir)
    if os.path.exists(cache_loc):
        filename = os.path.basename(cache_loc)
        file_location = os.path.join(path, filename)
        try:
            os.link(cache_loc, file_location)
        except OSError, err:
            if err.errno == errno.EXDEV:
                shutil.copy(cache_loc, file_location)
            if err.errno == errno.EEXIST:
                logging.info("Cached copy of %s already exists" % url)
            else:
                logging.exception("os.link failed")
    else:
        file_location = download(url, path)
        try:
            cache_dir = os.path.dirname(cache_loc)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            os.link(file_location, cache_loc)
        except OSError, err:
            #errno 18 is Invalid cross-device link
            if err.errno == 18:
                shutil.copy(file_location, cache_loc)
            else:
                logging.exception("os.link failed")
    return file_location

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
    logging.info('executing %r'%cmd)
    return os.system(cmd)

