.. _submit_job_help:

Job submission failure help
###########################

Device type X is not available
******************************

In the absence of other errors, this typically means that the submitted job
specifies a :term:`device type` which is not defined in the database for the
instance or is defined but only contains devices which have been
:term:`retired`.

No devices of type X are currently available to user Y
======================================================

A type of device unavailable error where the only available devices of the
specified :term:`device type` are restricted and the logged in user is not
allowed access to the restricted device. Contact the term:`device owner` if
there are queries.
