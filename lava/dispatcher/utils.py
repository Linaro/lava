#!/usr/bin/python
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
