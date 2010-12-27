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
        bundle = DocumentIO.load(stream)
        print "Loaded document type: %s" % bundle['format']

The error path is a little more complex. Loading can fail at the following levels:

1) You can get an IOError while reading from the stream
2) You can get a ValueError or JsonDecodeError depending on which version of
   simplejson you have while processing the text
3) You can get a DocumentFormatError when the format string is missing or has an unknown value
4) You can get a ValidationError when the document does not match the format 

Saving a document
=================

TODO


Checking document for errors
============================

TODO


Converting older documents to current format
============================================

TODO
