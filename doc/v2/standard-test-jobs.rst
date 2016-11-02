.. index:: standard test jobs, gold standard test jobs

.. _using_gold_standard_files:

Gold standard test jobs
#######################

The next step after the :ref:`first example job <explain_first_job>`,
is to move on to *gold standard* test jobs. These include a test job
for QEMU and test jobs for readily available ARM devices like
*cubietruck* and *beaglebone-black*.

.. seealso:: :ref:`creating_gold_standard_files`

Test writers are strongly recommended to follow these examples to have a known
working setup for later test jobs. These standard test jobs are part of the
regular functional testing performed by the LAVA software team prior to each
release. If you have problems debugging a test job failure on any instance of
LAVA, your recommended first action is to submit the closest standard test job
and compare the results against other instances like
``staging.validation.linaro.org``. To make this easier, all test writers are
recommended to use version control for all test jobs and to keep a local copy
of the closest standard test job for quick reference.

.. note:: A gold standard deployment for one device type is not necessarily
   supported for a second device type. Some devices will never be able to
   support all deployment methods due to hardware constraints or the lack of
   kernel support. This is **not** a bug in LAVA. If a particular deployment is
   supported but not stable on a device type, there will not be a gold standard
   image for that deployment. Any issues in the images using such deployments
   on that type are entirely down to the test writer to fix.

.. note:: Device type templates and other instance-specific configuration could
   affect the standard test jobs on specific instances. If a standard test job
   fails, check with the admins for that particular instance. The standard
   tests described here use support in the default device-type templates
   shipped with LAVA and are routinely tested on
   ``staging.validation.linaro.org``.

.. index:: job metadata, metadata

.. _job_metadata:

Metadata
********

Standard test jobs include :term:`metadata` which links the test job back to
the build information, logs and scripts.

Metadata consists of a series of key value pairs where the key must be a single
word (no whitespace, underscores and hyphens are allowed). Keys must be unique
within the metadata.Keys used in metadata should be consistent across
particular groups of test jobs with data specific to that test job in the
value.

Ensure that you change the **metadata** to point at your local repository so
that you can easily distinguish between the results with and without your
modifications:

.. include:: examples/test-jobs/qemu-amd64-standard-jessie.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: # CONTEXT_BLOCK

Automated test jobs should always use the metadata to specify:

* the source repository of the job definition
* the path to the job definition within the source repository
* the details of the build
* links to the build logs
* links to the build scripts.

These details allow other users to adapt and modify the build artifacts for
further tests.

The set of gold standard jobs has been defined in association with the Linaro
QA team. These jobs will provide a known baseline for test definition writers,
in a similar manner to the way the existing QA test definitions provide a base
for more elaborate testing.

