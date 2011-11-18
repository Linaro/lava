Version History
***************

Version 1.7.1
=============
* Add a glossary section
* Add versiontools to install requires so that rtfd.org builds this right


Version 1.7
===========

* Document most of the :ref:`format_1_3_schema` schema and
  :ref:`format_1_3_docs` (recommended)
* Provide some example documents :ref:`examples`

Version 1.6
===========

* Add support for 1.3 format. This format makes it possible to tag test runs
  with arbitrary tag names. Tagging allows one to organize results more flexibly.

Version 1.5
===========

* Add support for 1.2 format. This format makes attachments more flexible by
  allowing one to omit the contents of the attachment and store a public URL
  instead
* Allow 'svn' version control systems in source references
  (schema.properties.test_runs.items.properties.software_context.properties.sources.items.properties.branch_vcs.enum)
* Move everything away from __init__.py so that we can safely import it in setup.py

Version 1.4
===========

* Add support for DocumentIO.loads() and load() retain_order keyword argument.
  It defaults to True (preserving old behavior) and allows for either safe
  load-modify-save cycles that minimise differences or more efficient
  processing as plain python dictionaries.
* Add support for DocumentIO.dumps() and dump() human_readable keyword
  argument.  It defaults to True (preserving old behavior) and allows to
  control the desired format of the output document. For machine processing or
  storage the compact option will save a few bytes.
* Add support for DocumentIO.dumps() and dump() sort_keys keyword argument.  It
  defaults to False (preserving old behavior) and allows to create predictable
  documents from plain python dictionaries that would otherwise result in
  random ordering depending on python implementation details.


Version 1.3
===========

* Add mime_type support to attachments in 1.1 format. Seal the 1.1 format.
* Add support for document evolution for between 1.0.1 and 1.1 formats.
* More unit tests (evolution from 1.0.1 to 1.1, lossless IO fro 1.1 format)


Version 1.2
===========

* New document format with support for binary attachments and precise
  source information (extended software context)
* Refresh installation instructions to point to the new PPA, provide links to
  lp.net project page and pypi project page.

Version 1.1.1
=============

* Sign source package
* Fix installation problem with pip due to versiontools not being available
  when parsing initial setup.py

Version 1.1
===========

* Project renamed to linaro-dashboard-bundle
* Started using pypi for hosting releases and documentation


Version 1.0
===========

* First public release
