"""
Module with some interface for a degree of portability between different
JSON implementations available with different python versions.
"""

# XXX: This is quite annoying as there _are_ differences between them
# that break unit tests on python2.5 vs 2.6 vs 2.7. Consider dropping
# one good JSON library as bundled dependency since this is such a core
# feature is should not break randomly.
try:
    import json
except ImportError:
    import simplejson as json
