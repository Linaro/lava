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

import os
import shutil
import urllib2
import urlparse

from lava.dispatcher.config import LAVA_CACHEDIR

def download(url, path=""):
    urlpath = urlparse.urlsplit(url).path
    filename = os.path.basename(urlpath)
    if path:
        filename = os.path.join(path,filename)
    fd = open(filename, "w")
    try:
        response = urllib2.urlopen(urllib2.quote(url, safe=":/"))
        fd = open(filename, 'wb')
        shutil.copyfileobj(response,fd,0x10000)
        fd.close()
        response.close()
    except:
        raise RuntimeError("Could not retrieve %s" % url)
    return filename

def download_with_cache(url, path=""):
    cache_loc = url_to_cache(url)
    if os.path.exists(cache_loc):
        filename = os.path.basename(cache_loc)
        file_location = os.path.join(path, filename)
        os.link(cache_loc, file_location)
    else:
        file_location = download(url, path)
        try:
            os.makedirs(os.path.dirname(cache_loc))
            os.link(file_location, cache_loc)
        except OSError, err:
            #errno 18 is Invalid cross-device link
            if err.errno == 18:
                shutil.copy(file_location, cache_loc)
            #If this fails for any other reason, it will be because
            #another test is pulling the same image at the same time,
            #so ignore
    return file_location

def url_to_cache(url):
    url_parts = urlparse.urlsplit(url)
    path = os.path.join(LAVA_CACHEDIR, url_parts.netloc,
        url_parts.path.lstrip(os.sep))
    return path
