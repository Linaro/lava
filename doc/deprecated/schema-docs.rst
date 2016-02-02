.. _format_1_3_docs:

Schema Description (1.3)
************************

This document specifies the semantics of the 1.3 format.

Root object
^^^^^^^^^^^

The root object contains only two properties.

1. The format specified (``format``)
2. The array of test runs (``test_runs``).

The format needs to be a fixed value, namely the string ``"Dashboard Bundle
Format 1.3"``. The test array must have zero or more test run objects.


Test run objects
^^^^^^^^^^^^^^^^

This is the most fundamental piece of actual data. Test runs represent an act
of running a test (a collection of logical test cases wrapped in a testing
program) in a specific hardware context (currently constrained to a single
machine) and software context (currently constrained to installed software
packages and abstract source references, described later)

Each test run has multiple mandatory and a few more optional properties. The
mandatory properties are as follows:

1. The unique identifier assigned by the log analyzer
   (``analyzer_assigned_uuid``). Historically each test run was created by
   analyzing the text output of a test program. The analyzer was the only
   entity that we could control so it had to assign identifiers to test run
   instances. This identifier must be an UUID (that is, a string of 36
   hexadecimal characters in the following format
   ``[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}``. While
   upper and lower case letters are not distinguished lowercase values are
   preferred.

2. Analyzer time-stamp (``analyzer_assigned_date``). This one of the few time
   stamps stored in a bundle.  This one is authoritatively assigned by the log
   analyzer. It does not indicate when a test was actually started but rather
   when it was read and processed by the analyzer. 

3. Time check performed by the log analyzer (``time_check_performed``). Since
   LAVA uses analyzers that often run on the target device the value of the
   ``analyzer_assigned_date`` field was inherently unreliable. To
   differentiate between a device that has somewhat trusted time and date
   settings (such as a device running NTP service and having battery-powered
   real-time clock) from others we have introduced this boolean field. The
   interpretation remains open to the user but whenever one creates test run
   object it should be set to false unless the time can be trusted enough.

4. A free-form collection of attributes (``attributes``). This is a simple
   object with arbitrary properties. It can be used as a simple extension
   point to append data that test runs cannot natively represent. To make this
   field database friendly it has been limited to a string-only values. That
   is, each property can be named freely but must point to a string value.  In
   particular nested objects are not allowed.

5. An array of tags (``tags``). Each tag is a string in the following format:
   ``[a-z0-9-]+``. There should be no duplicates in the list although this is
   not enforced at format level yet.

6. Test identifier (``test_id``). Test identifier is an unique string that
   designates a test. Tests are simply a logical container of test cases. The
   identifier must be a string matching the following regular expression
   ``[a-z0-9.-]+``. It is recommended that reverse domain name scheme is used
   for test ID. Following this pattern would allow one to construct logical
   containers rooted at the top-level-domain owned by test owner.

6. An array of test results (``test_results``). Test results are described in
   a dedicated section below.

7. An array of attachments (``attachments``). Attachments are also described
   in a dedicated section below. It is worth mentioning that the format for
   storing attachments has changed and was different in 1.1 format and
   earlier. When processing unknown documents make sure to validate and evolve
   the format to the one that is recognized by your program.

8. The hardware context in which the test was invoked (``hardware_context``).

9. The software context in which the test was invoked (``software_context``).


Test results objects
^^^^^^^^^^^^^^^^^^^^

Test result is an object with three essential and many less used properties.
The most important properties are:

1. ``test_case_id`` that identifies the test case (the test case identifier is
   a string, unique to the test it belongs to, the test is recored, as
   ``test_id`` in a test run object)
2. ``result`` that encodes the outcome of the test. Currently only four values
   are allowed here, they are 'pass', 'fail', 'skip' and 'unknown'. The first
   three are rather obvious, the last one has a special purpose. It is the
   recommended value of a benchmark. Essentially since benchmarks are not
   pass-fail tests (the measurements can be dissatisfying from a certain point
   of view but this is relative) and the result code is mandatory we have
   decided to use it by default for all benchmarks. 
3. ``measurement`` (optional) that encodes the benchmark result. This is a
   single decimal number. The system handles this without precision loss so
   don't be afraid to use it for things that would be impractical with simple
   floating point numbers.

Since there is only one measurement allowed per test case our recommendation is
to store each measurement (each number that comes out of some test code) as a
separate result with an unique test case identifier. The only exception,
perhaps, would be a case where the test case is really the same and subsequent
results sample the same value periodically. We have not explored this area yet
and it is likely that for profiling we'll introduce a dedicated schema.

Attachments objects
^^^^^^^^^^^^^^^^^^^

Attachments are simple objects that store the ``pathname`` (or just name),
``mime_type`` and either the raw ``content`` (here stored as base64-encoded
string) or a reference to a copy in a ``public_url`` field.

We don't recommend storing very large attachments directly in the bundle. While
it will work the performance of handling such bundles will pale in comparison
to the same bundle with attachments stored externally.

Software context objects
^^^^^^^^^^^^^^^^^^^^^^^^

Software context is a object that describes the "software" part of the
environment in which a test was running. Currently this is limited to three
pieces of information:

1. A list of packages that was installed (``packages``). Each package is a
   simple object with ``name`` and ``version``. So far we used this system for
   Debian packages but it should map fine for RedHat and Android as well.

2. A list of software sources. A source is a loose association (it does not
   tell you exactly how the source was used/present on the device) between the
   test and some precise source code. The source code is identified by a
   particular commit (revision, check-in, change set, recored as
   ``branch_revision``) in a particular version control system (``branch_vcs``)
   that is found at a particular, version control system specific, url
   (``branch_url``). Since many of our users use Launchpad we also decided to
   store the name of the project. Thus we associated the ``project_name``
   property with a launchpad project name. There is one extra attribute, that
   is optional, which records the date and time of the commit
   (``commit_timestamp``). While we realise that time stamps do not form an
   ancestor-descendant chain (definitely not in distributed version control
   systems) they non the less provide useful context.

3. A name of the system ``image``. There is very little rationale behind this
   field apart from end-user usefulness (what was the user running?). We
   recommend to store the output of ``lsb_release --description --short`` if
   appropriate. Note that this does not allow one to uniquely identify images
   (at the very least this was not the indented usage of this field)


Hardware context objects
^^^^^^^^^^^^^^^^^^^^^^^^

Hardware context is an object that holds an array of devices in its sole
property (``devices``). Each device object has a type (``device_type``), a
human-readable description (``device_description``) and an arbitrary set of
attributes (contained in ``attributes``). Each attribute may be a string or an
integer.

There are some device types currently used by LAVA. The convention is "device,
dot, device type", for example we currently have ``device.usb``, ``device.cpu``
and ``device.memory``.

In practice devices are modeled ad-hoc, as the need arises. The attributes can
store enough information to be looked up later that we did not try to
standardize how all actual devices should be described (there is no strict
schema for, say, PCI cards). We hope to see a set of mini-standards developing
around this concept where a device of a particular class has a standardized set
of attributes that everyone agrees on.
