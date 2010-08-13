#!/usr/bin/python

def find_sources():
    import os
    import sys
    base_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..")
    if os.path.exists(os.path.join(base_path, "launch_control")):
        sys.path.append(base_path)

find_sources()

from django.core.management import execute_manager
try:
    import settings # Assumed to be in the same directory.
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

if __name__ == "__main__":
    execute_manager(settings)
