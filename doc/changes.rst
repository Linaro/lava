Version History
***************

.. _version_0_16:

Version 0.16
============
* Set the DJANGO_SETTINGS_MODULE env variable for sub processes

.. _version_0_15:

Version 0.15
============

* Allow settings.conf to define OPENID_LAUNCHPAD_TEAMS_MAPPING.
* Added configurable OpenID redirect domain support for login.

.. _version_0_14:

Version 0.14
============
* Allow the creating of DataTablesTables backed by sequences rather
  than querysets.

.. _version_0_13:

Version 0.13
============
* Work with Django 1.4
* Only offer to log in with openid if openid is enabled.
* Read SERVER_EMAIL from the settings.conf file.
* Fix a template bug encountered during the password reset process.

.. _version_0_12:

Version 0.12
============

* Merge 0.11.1 release branch
* django-tables2 dependency fix
* ajex_table.html dependency fix

.. _version_0_11_1:

Version 0.11.1
==============

* Drop a copy of lava-utils-interface and add a dependency on the external
  module. This makes lava-server co-installable with lava-utils-interface

.. _version_0_11:

Version 0.11
============
* Add code developed in lava-scheduler for super easy ajax-based pagination of
  tables.

.. _version_0_10_1:

Version 0.10.1
==============

* Enable OPENID_LAUNCHPAD_TEAMS_MAPPING_AUTO
* Avoid evaluating the full queryset when handling request for the
  data in a server-side driven table.

.. _version_0_10:

Version 0.10
============
Add scaffolding for server side pagination of tables
improve error 500 handler page
Merge HeadlesExtension and documentation update
add initial support for data-tables server side code

.. _version_0_9_1:

Version 0.9.1
=============

* Add :class:`lava_server.extension.HeadlessExtension`. This class is helpful
  for writing GUI-less extensions for LAVA.
* Small documentation cleanup
* Initial code reference

.. _version_0_9:

Version 0.9
===========

* Added support for data-tables serverside code
* LAVA Server now depends on django-1.3
* Fixed bugs 915314, 915293

.. _version_0_8_2:

Version 0.8.2
=============

* Fix the default mount point to be ""
* Make extensions aware of mount points

.. _version_0_7_2:

Version 0.7.2
=============

* Fix width of output in scheduler app
* fix wrapping issue with code blocks
* Add some documenation for lava-server
* Make the user menu stay inside the window on FF 3.6
* Use user nickname when real name is empty
* Better compatibility with older firefox
* Add .svg files to manifes
* Fix sign-in/sign-out menu
