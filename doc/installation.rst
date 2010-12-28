Installation
============

There are several installation optins available:


Using Ubuntu PPAs
-----------------

For Ubuntu 10.04 onward there is a stable and unstable PPA (personal package
archives):

* ppa:linaro-infrastructure/launch-control
* ppa:linaro-infrastructure/launch-control-snapshots

The stable PPA has normal releases, the unstable PPA has daily development
snapshots and is not recommended unless you need a bleeding edge feature.

    sudo add-apt-repository ppa:linaro-infrastructure/launch-control

After you add the PPA you wish you need to update your package cache

    sudo apt-get update

And you can install the package, it is called `python-linaro-dashboard-bundle`

    sudo apt-get install python-linaro-dashboard-bundle


Using Python Package Index
--------------------------

This package is being actively maintained and published in the `Python Package
Index <http://http://pypi.python.org>`_. You can install it if you have `pip
<http://pip.openplans.org/>`_ tool using just one line:

    pip install linaro-python-dashboard-bundle


Installing from source
----------------------

To install from source you must first obtain a source tarball from either pypi
or from launchpad. To install the package unpack the tarball and do:

python setup.py install

You can pass --user if you prefer to do a local (non system-wide) installation.
