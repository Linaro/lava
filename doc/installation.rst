Installation
============

Prerequisites
^^^^^^^^^^^^^

This package has the following prerequisites:

* linaro-json
* simplejson
* versiontools

To run the test suite you will also need:

* testtools
* testscenarios

To build the documentation from source you will also need:

* sphinx

Installation Options
^^^^^^^^^^^^^^^^^^^^

There are several installation options available:

Using Ubuntu PPAs
-----------------

For Ubuntu 10.04 onward there is a PPA (personal package archive):

* ppa:linaro-validation/ppa

This PPA has only stable releases. To add it to an Ubuntu system use the
add-apt-repository command::

    sudo add-apt-repository ppa:linaro-validation/ppa

After you add the PPA you need to update your package cache::

    sudo apt-get update

Finally you can install the package, it is called `python-linaro-dashboard-bundle`::

    sudo apt-get install python-linaro-dashboard-bundle


Using Python Package Index
--------------------------

This package is being actively maintained and published in the `Python Package
Index <http://pypi.python.org>`_. You can install it if you have `pip
<http://pip.openplans.org/>`_ tool using just one line::

    pip install linaro-dashboard-bundle


Using source tarball
--------------------

To install from source you must first obtain a source tarball from either `pypi
project page <http://pypi.python.org/pypi/linaro-dashboard-bundle>`_ or from
`Launchpad project page
<http://launchpad.net/linaro-python-dashboard-bundle>`_.  To install the
package unpack the tarball and run::

    python setup.py install

You can pass --user if you prefer to do a local (non system-wide) installation.

..  note:: 

    To install from source you will need distutils (replacement of setuptools)
    They are typically installed on any Linux system with python but on Windows
    you may need to install that separately.
