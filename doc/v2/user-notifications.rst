.. index:: user notifications, notifications

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
  canceled) and the type (regression, progression). There is a special status of
  'finished', which will match any of (complete, incomplete, canceled).

The basic **email** template includes job details, device details and results,
based on the level of **verbosity** (``verbose``, ``quiet``, ``status-only``).
verbose level job information will only be included if the job finished as
complete or incomplete, not when the job was canceled.

Notification recipients
=======================

The method and destination of each notification can be set for each recipient.
Currently, two notification methods are supported, **email** and **IRC**.

Recipients can be specified using the LAVA username or in full.

If the **recipients** section is omitted in the notify block, the system will
send an email to the job submitter only, provided the **criteria** is satisfied,
and there is no **callbacks** section.

Notification callbacks
======================

In addition to sending email and IRC messages to **recipients**, the system can
send multiple URL callback actions. This will do a GET or POST request to the
specified URL in the **callbacks** subsection. This can be used to trigger some
action remotely. If a callback uses the POST request, the system will attach job data as described below.
The **callbacks** section supports list of the following options:

* **url** The URL for the request. This also supports field value
  substitution, i.e. in http://example.com/{ID}/{STATUS} **id** and
  **status** will be replaced with corresponding values from the job.

* **method** GET or POST

* **token** This option is used to supply the API token of the
  authenticated user, appended as the POST request parameter. If the submitting
  user has an XMLRPC auth token with a description that matches this field, that
  token is returned instead. The token is included in the POST data, and also in
  an Authorization header.

* **header** In case **token** is defined this option gives possibility to define
  custom header to be used instead of Authorization.

* **dataset** This option specifies style of data that the system
  will provide in the callback. It applies only for the POST request. The format
  of the data and possible options are as following:

  * **minimal** This will provide basic job info such as job id, status,
    submit_time, start_time, end_time, submitter_username,
    failure_comment, priority, description, actual_device_id, definition and
    metadata.
  * **logs** In addition to minimal data this will also attach the job log
    output in the url encoded format
  * **results** In addition to minimal data this will also attach the job
    results as a list of test suites exported in yaml format.
  * **all** In addition to minimal data this will include both the **logs** and
    **results** datasets as described above.

* **content-type** This option is used to determine how the POST data is submitted:

  * **urlencoded** (Default) Will return a standard HTTP POST request, with an
    application/x-www-form-urlencoded Content-Type header and data sent as an
    urlencoded query string.
  * **json** The data is dumped into JSON and returned with a ``Content-Type:
    application/json`` header.

Example callback usage:

.. include:: examples/source/notifications.yaml
   :code: yaml
   :start-after: # notify callbacks block

.. _debugging_callback:

Debugging notification callbacks
--------------------------------

The job data can also be retrieved using the :ref:`REST API <rest_api>` (which
supports authentication). For example::

 $ wget -O job_data.gz http://localhost/scheduler/job/2126/job_data

 $ wget -O job_data.gz "http://localhost/scheduler/job/2127/job_data?user=neil&token=22yj3ls...."

Returns a gzip file containing the job data as JSON.

.. note:: Only test jobs which are configured to use the notification callback
   will create notification callback data for later retrieval. Other jobs will
   generate a 404 error.

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
verbosity, so some options which are present in the ``notify`` block for email
recipients do not apply for IRC recipients, like **comparing** options and
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
   :end-before: # notify callbacks block
