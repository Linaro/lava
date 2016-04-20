.. index:: developing new classes

.. _developing_new_classes:

Developing new classes for LAVA V2
##################################

Where to start?
***************

Test with simple scripts
========================

#. Prove that your idea of a test job actually works on the hardware
#. Build the requirements of automation into your tests

   #. Consider the needs of a serial console.
   #. Think about all the steps, including temporary paths
   #. Write a simple script that covers all the steps.

Start with new classes
======================

For a completely new strategy, new classes are often best going
into new files. Follow the example of existing files but concentrate
on just the ``__init__`` functions and imports at this stage. Adding
the summary and description elements should help you identify how to divide the
work between the classes.

Add support files for unit tests
================================

#. Create a device configuration YAML file with the help of
   the `Online YAML parser <http://yaml-online-parser.appspot.com/?yaml=&type=json>`_
   using examples of existing files.
#. Create a job submission YAML file, again with the parser and existing
   examples.

At each stage, consider which elements of the job and device configuration
may need to be overridden by test writers and instance admins.

Add unit tests
==============

It may seem strange to add one or more unit test files at this stage but it helps
write the validate functions which come up next. Adapt an existing Factory
class to load the device configuration file and sample job file and then
create a Job. In the test cases, inspect the pipeline created from these
YAML files. Whenever the validate or populate functions are modified,
add checks to the unit test that the new data exists in the correct type
and content. Re-run the unit test each time to spot regressions.

Run all the unit tests
======================

There are a number of unit tests which parse all jobs and devices in
the test directories, so ensure that the new additions do not interfere
with the existing tests. This is the basis of what needs to go into the
``accepts`` function of the Strategy class and into the job and device
YAML. Make sure that there is sufficient differentiation between the new
files and the existing files without causing duplication.

Incorporate the test script into the classes
============================================

If the new classes are properly aligned with the workload of the test job,
the sections of the test script will fall naturally into the classes in
the same sequence.

* Handle all of the static data from ``parameters`` in the ``validate``
  function. It is often useful to assemble some these parameters into
  member variables, checking that the final form is correct in the
  test case.
* Only use ``self.errors`` in ``validate`` instead of raising an exception
  of allowing calls within ``validate`` from raising unhandled exceptions.
  If ``validate`` should not continue executing after a particular error,
  always ensure that an error is set before returning from ``validate``
  early.
* Test that all of the parameters appear in the class in the correct
  type and with the correct content after running ``job.validate()``.
  The simplest way to do this is to inspect the ``job.pipeline.actions``
  using a list comprehension based on the action ``name``.
* Handle only dynamic data in the ``run`` function (which does not need
  to be completed at this stage).
* Separate constants from parameters. ``utils.constants`` will provide
  a way for instance admins to make changes. If there is a chance
  that either a different device-type or a different test job plan,
  then add the default to the job or device file and fetch the value
  in the parameters. Ensure that ``validate`` shows that the correct
  value is available.
* Use existing classes where the support ``just works``, e.g. by adding
  ``DownloadAction`` to a ``populate`` function.

Check the new classes
=====================

``pylint`` can be annoying but it is also useful - providing that some
of the warnings and errors are disabled. Check similar files but do be
cautious about disabling lots of warnings in the early stages. Pay
particular attention to missing imports, unused variables, unused imports,
and invalid names. Logging not lazy is less relevant, overall, in the LAVA
codebase - there are situations where lazy logging results in the wrong
values being entered into the logs.

.. warning:: ``pep8`` is essential - no reviews will be accepted if there
   are ``pep8`` errors beyond ``line-too-long`` (E501). This is the first
   check performed by ``./ci-run`` (which must also pass).

Startup achieved
================

From this point, standard code development takes over. To get the code
accepted, some guidelines must be followed:

* ``./ci-run`` must complete without errors
* Every set of new classes should have some unit tests.
* Every new Strategy **must** have new unit tests.
* Part of the review will be whether the unit tests have sufficient
  coverage of the new code and possible side-effects with existing code.
