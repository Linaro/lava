Migration Status
################

.. seealso:: :ref:`admin_introduction` and :ref:`migrating_to_pipeline`

Active devices in this context are defined as:

#. Device status is not :term:`RETIRED <retired>`.

#. Device type for this device has ``Display`` set to True.

For health checks, devices where the health check has been disabled are
excluded.

.. seealso:: :ref:`health_checks`

Migration of active V1 devices to V2
====================================

Shows 100% completion when all active devices in the database have
``is_pipeline`` set to True.

If incomplete, a list of active devices still using V1 will be displayed.

.. seealso:: :ref:`django_admin_interface`

Active devices exclusive to V2
==============================

Shows 100% completion when all active devices in the database are set to
:term:`exclusive` in the :term:`device dictionary`.

If incomplete, a list of active devices which are not exclusive to V2 will
be displayed.

.. seealso:: :ref:`admin_device_dictionary`

Migration of active devices to V2 healthchecks
==============================================

Shows 100% completion when all device-types of active devices have had the
health check job definition cleared from the database.

If incomplete, a list of active devices still using healthchecks in the
database will be displayed. The :term:`device type` of these devices will need
to be checked.

.. seealso:: :ref:`django_admin_interface`

Active devices with healthchecks
================================

Shows 100% completion when health checks exist in
``/etc/lava-server/dispatcher-config/health-checks`` for all active devices in
the database.

If incomplete, a list of active devices without healthchecks will be
displayed, together with the name of the relevant V2 health check which the
device would use.

.. note:: Unlike the other migration checks, this one does **not** need to be
   100% complete before support for V1 submissions is disabled as long as the
   devices concerned are :term:`exclusive` and other measures are at 100%.
