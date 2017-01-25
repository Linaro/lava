.. index:: user notifications

.. _notifications:

User notifications in LAVA
##########################

Users can receive notifications containing information about submitted test
jobs and the accompanying results by using settings in job definition yaml.
Users can also compare the job results within notifications against previous
results which satisfy certain conditions.

The basic setup of the ``notify`` block in job definitions will have
**criteria**, **verbosity**, **recipients** and **compare** blocks.

* **Criteria** tells the system when the notifications should be sent.

* **verbosity** will tell the system how detailed the email notification should
  be.

* **Criteria** can be set by job status (running, complete, incomplete,
  canceled) and the type (regression, progression).

The basic **email** template includes job details, device details and results,
based on the level of **verbosity** (``verbose``, ``quiet``, ``status-only``).

Notification recipients
=======================

The method and destination of each notification can be set for each recipient.
Currently, two notification methods are supported, **email** and **IRC**.

Recipients can be specified using the LAVA username or in full.

Using profile settings
----------------------

LAVA users can configure the ``IRC settings`` or email address in their own
profile data in the instance. This allows the recipient to be specified using
only the LAVA username.

.. image:: images/profile-menu.png

Direct listing of recipients
-----------------------------

If the user has not configured their own profile data, the recipient details
must be specified in full.

Examples for user vs manual addressing:

.. include:: examples/source/notifications.yaml
   :code: yaml
   :start-after: # notify recipients block
   :end-before: # notify compare block

IRC and email notifications use different templates since emails allow for more
verbosity, so some options which are present in notify block for email
recipients will be obsolete for IRC recipients, like **comparing** options and
**verbosity**.


Result comparison in notifications
==================================

Users can use notifications to compare the job status against the last few jobs
and also compare job results, like test case/suites difference. The
notification will report if there are new test cases compared to previous test
jobs, if there are some missing and how the said results differ.

Which test jobs the current one is compared to is determined by the
:ref:`queries` system, where those previous jobs will be taken from the query
specified in the notification block. Custom queries (:ref:`query_by_url`) can
also be specified.

**Blacklisting** test cases is also an option. Ignoring some of the test cases
in the comparing section of the notification is possible through an option in
the notification block.

Here are some comparing setup examples from test definition excerpts:

.. include:: examples/source/notifications.yaml
   :code: yaml
   :start-after: # notify compare block
   :end-before: # notify compare custom block

.. include:: examples/source/notifications.yaml
   :code: yaml
   :start-after: # notify compare custom block

