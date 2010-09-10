"""
Dashboard Application (package)
"""

__version__ = (0, 2, 0, "dev", 0)


def get_version():
    return ".".join(map(str, __version__))
