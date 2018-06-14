.. index:: jinja2 templating, generating test job submissions

.. _jinja_templating:

Using Jinja2 to generate LAVA test job submissions
##################################################

.. seealso:: http://jinja.pocoo.org/docs/dev/

LAVA is just one part of a complete CI solution. There will be other
automated steps feeding data into LAVA, and often other automated steps
retrieving data from LAVA to provide information to developers.

.. seealso:: :ref:`ci_loop`

Retrieving data from LAVA typically involves using some of the metadata
included in the original submission, for example the commit hash of the
change which triggered the build used in this test job. Other metadata
like the kernel branch, test series and source location also become
important.

Changing the commit hash manually or semi-automatically using ``sed``
etc. is possible but does not scale. Although the test job submission
is in YAML, editing the test job submission after loading YAML into a
language like Python means that all the useful comments are lost.

A better solution is to use a simple templating language to generate
the YAML job submissions. LAVA already uses ``Jinja2`` for device
dictionaries and device-type templates, so it is a natural next step to
use it when creating job submissions too. As a bonus, the jinja syntax
is also very similar to the markup used within Django - a lot of
developers are familiar with it.

.. _templates_starting:

Starting with templates
***********************

**The format you start with, is the format you will output.**

Any YAML file can be a starting template. Jinja2 will only operate
directly on text which is written in Jinja2 syntax. Anything else will
be passed through **unaltered**. This has two valuable properties for
our YAML job submissions: comments are preserved, and the ordering of
items (dictionaries, etc.) will be kept.

The same cannot be said if you load YAML data into a Python program
directly, e.g:

.. code-block:: yaml

 # example dictionary
 first_key: 1
 second_key: 2
 third_key: 3
 fourth_key: 4

Loading this snippet (a YAML dictionary) into Python2 will generate::

 {'second_key': 2, 'third_key': 3, 'fourth_key': 4, 'first_key': 1}

Loading the same snippet into Python3 will generate::

 {'first_key': 1, 'second_key': 2, 'third_key': 3, 'fourth_key': 4}

Loading this as a template would generate:

.. code-block:: yaml

 # example dictionary
 first_key: 1
 second_key: 2
 third_key: 3
 fourth_key: 4

To make a change in that output, we save the template to a file and add
some Jinja2 syntax to the template:

.. literalinclude:: examples/templates/content.jinja2
     :language: yaml
     :linenos:
     :lines: 1-5
     :emphasize-lines: 2

Download or view the complete example:
`examples/templates/content.jinja2 <examples/templates/content.jinja2>`_

Data is then presented as a ``details.jinja`` dictionary:

.. literalinclude:: examples/templates/details.jinja2
     :language: jinja
     :linenos:
     :lines: 1-2
     :emphasize-lines: 2

Download or view the complete example:
`examples/templates/details.jinja2 <examples/templates/details.jinja2>`_

The python script to process the template is based on the LAVA source
code and only requires Jinja2:

https://git.lavasoftware.org/lava/lava/blob/master/lava_scheduler_app/tests/test_base_templates.py#L22

.. literalinclude:: examples/templates/templating.py
     :language: python
     :linenos:
     :lines: 35-52
     :emphasize-lines: 12

Download or view the complete example:
`examples/templates/templating.py <examples/templates/templating.py>`_

The ``templating.py`` script loads the details data as a dictionary
(line 12) and then looks up the ``content.jinja2`` as the **extended**
template, based on the ``CONFIG_PATH``. (The template can easily be in
a different directory to the details dictionary.)

Output
======

.. code-block:: yaml

 # example dictionary
 first_key: 15
 second_key: 2
 third_key: 3
 fourth_key: 4

.. index:: templating - contexts, templating - overrides

.. _template_contexts:

Extending templates with contexts
*********************************

``templating.py`` above includes a ``job_ctx`` dictionary which sets a
different value but this value is currently ignored. This is because
the details dictionary sets ``first_key`` without allowing for an
override.

This is a key part of how templating works with Jinja2. Each element
controls the ability of the next element to provide overrides or
changes.

#. **hard coded template values** - nothing can override the raw YAML
   of the template itself. In the example for this section,
   ``content.jinja2`` contains a YAML comment and a basic YAML
   dictionary. **Anything** (including whitespace) in the template
   which is not marked up with Jinja2 syntax will be preserved in the
   final output unchanged and without an ability to support changes via
   the details dictionary or the job context.

#. **template defaults** - templates can include default values:

   .. code-block:: jinja

    first_key: {{ first_key | default(4) }}

   If neither the details dictionary nor the job context set a value
   for ``first_key``, the default from the template will be used. In
   the original ``content.jinja2``, there is no default. If the details
   dictionary and job context do not override ``first_key``, the value
   will be left blank:

   .. code-block:: yaml

    first_key:

   If this output is then loaded into Python as a YAML file, the value
   of the ``first_key`` key in the Python dictionary would be ``None``.

#. **details dictionary values** - in the example above, the details
   dictionary sets a value of ``15`` and the job context cannot change
   that value.

   It is also possible to add new blocks of YAML output using the same
   ``set`` function of the details dictionary. Take care with the
   whitespace in such dictionaries. **Always** test the output and
   verify not only that the output is valid YAML but that when loaded
   into Python, that the dictionary contains the correct values for the
   correct keys. Whitespace problems are a common cause of errors. It's
   easy to cause invalid syntax in the output, or for a value to be
   assigned in the wrong place (as a value for a sub key instead of as
   a new key, or vice versa).

   .. code-block:: python

    {key: value}
    # not the same as:
    {key: None, value: None}

   Details dictionary values can be other Python types. It is common to
   find strings, floats, lists and dictionaries. Syntax can be either
   Python or YAML.

#. **details dictionary defaults** - the details dictionary can use
   defaults in the same way as the template:

   .. code-block:: jinja

    {% set first_key = first_key | default(15) %}

   This allows a value in the job context to override the value.
   Download the example files and edit ``details.jinja2`` to set the
   value ``15`` but only as a default. Re-run ``templating.py`` and
   the job context value of ``9`` will be used in the output instead:

   .. code-block:: yaml

    # example dictionary
    first_key: 9
    second_key: 2
    third_key: 3
    fourth_key: 4

#. **job context** - To set a value in the job context, there must be a
   placeholder in the template and usually a default value as well.

.. _templates_extend_templates:

Templates can extend templates
******************************

Once you have more than a couple of related templates, it becomes
obvious that some content will be duplicated across many of those
templates. Create a new template (possibly using the conventions of
``base-foo`` or ``foo-common``) containing a single copy of the base
content and then each template simply ``{% extends 'base.jinja2' %}``.

.. _templates_logic:

Logic control within templates
******************************

Jinja2 supports a range of logical elements, for example:

.. code-block:: jinja

 {% for a in b %}
 {% endfor %}

 {% if a is b %}
 {% endif %}

 {% block label %}
 {% endblock %}

See the Jinja documentation and the LAVA device-type templates for
more examples.

.. index:: templating - best practice

.. _template_best_practice:

Template best practice
**********************

Here are some recommendations on how to use templates effectively with
LAVA job submissions.

* **Avoid repetition** - of content or logic.

* **Avoid complexity** - keep the number of possible overrides,
  defaults and templates to a workable level.

* **Keep the YAML in the templates** - the structure of the final
  output should be visible directly from the template, subject to
  templates extending other templates. The details dictionary should
  ideally contain only Jinja2 syntax content. This makes it much easier
  to verify that the templates will always produce valid YAML.

* **Build tests alongside the templates** - check that every template
  outputs valid YAML on it's own, with example details dictionaries and
  with example job contexts.

* **Use version control** - templates can quickly become complex. Make
  sure errors can be traced and triaged against the history of changes.

* **Keep the output human readable** - use **Comments** liberally to
  describe the content, particularly when using logic in templates.
  Structure the YAML in a way that makes sense to humans. For example,
  for a LAVA Test Job submission, ``job_name`` and ``device_type`` are
  commonly at the top and the ``actions`` list follows at the end.
  A big advantage of templating is that comments and structure are
  preserved; use that to your advantage.

* **Use automated submission bots** - some habits are hard to break and
  many test writers will simply copy and paste a test job submission
  without changing either the job_name or the metadata. To be sure that
  you can retrieve only the data that was submitted via the templating,
  ensure that the output of the templates is submitted by an automated
  user and create sufficient automated users for each Test Plan or
  "Project" if multiple projects share a LAVA instance.
  
  This will allow you to easily filter results later.

* **Use checksums** - when referring to build artifacts like kernel
  binaries and filesystem images, include checksums for those artifacts
  in your job submission too. Most build systems can be configured to
  generate checksums at build time; use the job dictionary and
  templates to insert checksums. This will ensure that LAVA is using
  exactly what was specified for your test. This can be particularly
  important when network caches and proxies might affect what your
  system downloads.

* **Avoid using latest directory names** - again, specify **exactly**
  what artifacts your test will use, with **stable** URLs. It is a
  common and useful feature of build systems to include a
  human-friendly ``latest`` link in a download directory. However, what
  happens when the next build happens? The ``latest`` link now moves.
  You might not be able to determine later exactly which files were
  used in your test, and you will not be able to resubmit the same test
  in the future (for example if you want to debug some of your test
  definitions).

  Templating provides a simple way to refer to the exact file or
  directory that you need, to match the metadata you specify.

.. _templates_test_jobs:

Using templates for test jobs
*****************************

The specifics of how to build templates for test job submission will
depend on the data being provided by the rest of your CI system.

Common elements which would need to be modified by the details
dictionary (or job dictionary for test jobs) might be:

#. ``job_name``: Avoid making this cryptic or excessively long. The job
   name is meant to be human readable and is not well suited to
   searching or data analysis. Use ``metadata`` for that. Let the job
   name be a descriptive sentence which is sufficiently identifiable
   without having to include a mangled version of every identifier used
   in the CI process to this point.

#. ``metadata``: This is a free form dictionary which test writers can
   use to provide searchable key:value pairs which preserve all of the
   variables and generated dynamic data from the CI loop up to this
   point. Commit hashes, build numbers, branch names and URLs, series
   labels, name and/or URL of the configuration, build logs ...

#. ``urls``: when testing software using hardware, the software will be
   constantly changing. Templating is the best way to ensure that the
   URLs and the metadata for those URLs change in lockstep.
