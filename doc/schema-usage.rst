Usage
*****

Loading a document
==================

There are two functions that perform this task. For streams there is
:func:`DocumentIO.load`, for simple strings there is
:func:`DocumentIO.loads`.

Each function does three things:
 * read the document text
 * deserialize it properly (using propert configuration for parsing
   floating point numbers).
 * check the document by inspecting the format and validating it against
   a built-in schema

If you use this API there is no need to double-check the contents of
the document you've got. It's going to match the description of the
schema.

Example of reading something from a file::

    with open("bundle.json", "rt") as stream:
        format, bundle = DocumentIO.load(stream)
        print "Loaded document type: %s" % format 

The error path is a little more complex. Loading can fail at the following levels:

1) You can get an IOError while reading from the stream
2) You can get a ValueError or JsonDecodeError depending on which version of
   simplejson you have while processing the text
3) You can get a DocumentFormatError when the format string is missing or has an unknown value
4) You can get a ValidationError when the document does not match the format 

Saving a document
=================

There is just one function for saving a document
:func:`DocumentIO.dump`. It will always validate the document before
saving it so there is little chance of producing invalid files this way.

Currently this function uses a hardcoded human-readable profile. If you
care about representation efficiency use a compressed storage such as
:class:`gzip.GzipFile`.

Example of writing a bundle to a file::

    with open("bundle.json", "wt") as stream:
        bundle = {"format": "Dashboard Bundle Format 1.0"}
        DocumentIO.dump(stream, bundle)

Checking document for errors
============================

To validate document for correctness you can use
:func:`DocumentIO.check`.

.. note::
    Most of the time you don't need to validate a document explicitly.
    It is automatically validated when loading and saving.

Converting older documents to current format
============================================

To convert a document to the most recent format you can use
:func:`DocumentEvolution.evolve_document`. It is safe to call this
method on any valid document. If you just need to check if the document
is using the most recent format call
:func:`DocumentEvolution.is_latest`.
