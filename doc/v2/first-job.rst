.. index:: submit

.. _submit_first_job:

Submitting your first job
=========================

A job defines what software should be deployed on the ``device under
test`` (DUT) and what actions should be performed there. Jobs are
defined in *YAML* files.

Job Definition
--------------

Here's an example minimal job that you should be able to use right
away if you have user access to an appropriately-configured LAVA
installation.

.. code-block:: yaml

 # Sample JOB definition for an x86_64 QEMU
 device_type: qemu
 job_name: QEMU pipeline, first job

 timeouts:
   job:
     minutes: 15
   action:
     minutes: 5
 priority: medium
 visibility: public
 context:
   arch: amd64

 actions:
 - deploy:
   timeout:
     minutes: 5
   to: tmpfs
   images:
     rootfs:
       image_arg: -drive format=raw,file={rootfs}
       url: https://images.validation.linaro.org/kvm-debian-wheezy.img.gz
       compression: gz
   os: debian

 - boot:
   method: qemu
   media: tmpfs
   prompts: ["root@debian:"]

 - test:
   timeout:
     minutes: 5
   definitions:
   - repository: git://git.linaro.org/qa/test-definitions.git
     from: git
     path: ubuntu/smoke-tests-basic.yaml
     name: smoke-tests
   - repository: https://git.linaro.org/lava-team/lava-functional-tests.git
     from: git
     path: lava-test-shell/single-node/singlenode03.yaml
     name: singlenode-advanced

.. seealso:: :ref:`explain_first_job`.

.. _job_submission:

Job Submission
--------------

Jobs may be submitted to LAVA in one of three ways:

 * the command line (using the ``lava-tool`` program); or
 * the web UI; or
 * the XML-RPC API

.. note:: ``lava-tool`` is a general-purpose command line interface
	  for LAVA which can be used directly on the LAVA server
	  machines and also remotely on any computer running a
	  Debian-based distribution. See :ref:`lava_tool` for more
	  information.

For now, lava-tool is the easiest option to demonstrate. Once you have
copied the above job definition to a file, (for example
*/tmp/job.yaml*), use ``lava-tool`` to submit it as a test job in
Linaro's main LAVA lab:

::

  $ lava-tool submit-job https://<username>@validation.linaro.org/RPC2/
  /tmp/job.yaml
  Please enter password for encrypted keyring:
  submitted as job id: 82287

.. note:: Replace *username* with your username. Enter the password
          for the encrypted keyring which is the same that was used
          when adding the authentication token.

Once the job is submitted successfully, the job id is returned; this
may be used in order to check the status of the job via the web UI. In
the above submission the job id returned is 82287. Visit
``https://validation.linaro.org/scheduler/job/<job-id>`` in order to
see the details of the job run: the test device chosen, the test
results, etc.

FIXME
<graphic here, and some details of what you'll see>

.. index: test definitions

.. _test_definitions:

Test Definitions
----------------

.. note:: The following is crap, but we should have something
	  here I think. FIXME!

In order to run a test, a test definition is required. A test
definition is expressed in YAML format. A minimal test definition
would look something like the following:

.. code-block:: yaml

  metadata:
      name: passfail
      format: "Lava-Test-Shell Test Definition 1.0"
      description: "Pass/Fail test."
      version: 1.0

  run:
      steps:
          - "lava-test-case passtest --result pass"
          - "lava-test-case failtest --result pass"

In order to run the above test definition with a minimal job file, the
following job json could be used and submitted in the same way as
explained above:

.. code-block:: yaml

  run:
      steps:
          - "lava-test-case passtest --result pass"
          - "lava-test-case failtest --result pass"

.. index: results

.. downloading_results:

Downloading test results
------------------------

LAVA V2 makes the test results available directly from the instance,
without needing to go through ``lava-tool``. Currently, the results
for any test job can be downloaded as :abbr:`CSV (comma-separated value)`
and YAML format.

For example, the results for test job number 123 are available as
CSV using::

 https://validation.linaro.org/results/123/csv

The same results for job number 123 are available as YAML using::

 https://validation.linaro.org/results/123/yaml

If you know the test definition name, you can download the results for
that specific test definition only in the same way::

 https://validation.linaro.org/results/123/singlenode-advanced/csv
 https://validation.linaro.org/results/123/singlenode-advanced/yaml

Some test jobs can be restricted to particular users or groups of
users. The results of these test jobs are restricted in the same
way. To download these results, you will need to specify your username
and one of your :ref:`authentication_tokens` - remember to quote the
URL if using it on the command line or the & will likely be
interpreted by your shell::

 'https://validation.linaro.org/results/123/csv?user=user.name&token=yourtokentextgoeshereononeverylongline'

 $ curl 'https://validation.linaro.org/results/123/singlenode-advanced/yaml?user=user.name&token=yourtokentextgoeshereononeverylongline'

Use the **Username** as specified in `your Profile </me>`_ - this may
differ from the username you use when logging in with LDAP.

.. caution:: Take care of your tokens - avoid using personal tokens in
   scripts and test definitions or other files that end up in public
   git repositories. Wherever supported, use ``https://`` when using a
   token.

Web Based Job Submission
^^^^^^^^^^^^^^^^^^^^^^^^

**The web UI form does not yet support pipeline (V2) jobs; expect this
support to appear soon**.

.. commented out until the web ui support is available.

   Visit https://validation.linaro.org/scheduler/jobsubmit and paste your
   json file into the window and click "Submit" button. The job
   submission screen is shown below,

   .. image:: ./images/job-submission-screen.png

   .. note:: If a link to job json file is pasted on the above screen,
          the JSON file will be fetched and displayed in the text box
          for submission.

   Once the job is successfully submitted, the following screen appears,
   from which the user can navigate to the job details or the list of
   jobs page.

   .. image:: ./images/web-ui-job-submission-success.png

   Viewing the submitted job will show something like this.

   .. image:: ./images/job-details.png

XML-RPC Job Submission
^^^^^^^^^^^^^^^^^^^^^^

See <WHERE? FIXME> for details on how to use the XML-RPC API.

