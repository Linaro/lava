Dashboard Bundle Schema
***********************

Dashboard bundle is a JSON document. As such it can be transmitted,

manipulated and processed with various different tools, languages and
toolkits. 

This specification intends to formalize the schema of supported documents as
well as give additional insight into how each field was designed to be used.

Throughout this document we will be using path references. That is, starting
with the root object a sequence of traversals, either object access
(dictionary access in Python) or array access (list access in Python).

For array indices we will also use wild-card character ``*`` to indicate that
all indices of the specified array are considered equal.

.. toctree::
    :maxdepth: 2

    schema/docs.rst
    schema/changes.rst
    schema/raw.rst
    schema/examples.rst
