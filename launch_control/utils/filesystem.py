"""
Module with simple file system related utilities.

The code, while trivial, is moved here to simplify unit tests that
otherwise need to mock open() and all the associated context protocol
implementation.
"""

import gzip

def read_text_file(pathname):
    """
    Read a text file from the given path.

    If IOError or OSError are raised they are suppressed an None is
    returned instead.
    """
    return ''.join(read_lines_from_text_file(pathname))


def read_lines_from_text_file(pathname):
    if pathname.endswith(".gz"):
        stream = gzip.open(pathname, 'rt')
    else:
        stream = open(pathname, 'rt')
    try:
        for line in stream:
            yield line
    except (IOError, OSError) as ex:
        pass
    finally:
        stream.close()
