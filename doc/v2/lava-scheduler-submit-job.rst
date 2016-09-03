.. _submit_job_help:

Job submission failure help
###########################

Device type X is not available
******************************

In the absence of other errors, this typically means that the submitted JSON
specifies a :term:`device type` which is not defined in the database for the
instance or is defined but only contains devices which have been
:term:`retired`.

No devices of type X are currently available to user Y
======================================================

A type of device unavailable error where the only available devices of the
specified :term:`device type` are restricted and the logged in user is not
allowed access to the restricted device. Contact the term:`device owner` if
there are queries.

X is not allowed to submit to the restricted device Y
=====================================================

The submitted JSON requested a specific target device instead of a
:term:`device type` and this specific device is restricted by the :term:`device
owner`. Check the status page in LAVA to see if there are more devices of the
required type available or change the JSON to ask for a device type instead of
a specific target.
