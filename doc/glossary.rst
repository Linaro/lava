Glossary
********

LAVA uses various terminology that is sometimes confusing as many of the words
are commonly used and have many meanings. This glossary should help to
understand the rest of the documentation better.

Test
    A test is a piece of code that can be invoked to check something. LAVA
    assumes that each test has a unique identifier. A test is also a container
    of test cases.

Test Case
    A test case is a sub-structure of a Test. Typically individual test cases
    are separate functions or classes compiled into one test executable. Test
    cases have identifiers, similar to each test, however the test case
    identifier needs to be unique only among the test it is a part of.

Test Run
    A test run is an act of running a test on some hardware in some software
    (typically operating system kernel, set of installed and configured
    packages).

Bundle, results bundle
    A document format that can describe test results. The document is defined
    as a JSON document matching any of the version of the bundle schema
    :ref:`format_1_3_docs`

Software Context
    A non-exhaustive description of the software configuration of the device
    that is performing a test run.

Hardware Context
    A non-exhaustive description of the hardware configuration of the device
    that is performing a test run. One important aspect is that currently
    hardware context is limited to one device only.
