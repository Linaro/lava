# This file is part of the ARM Validation Dashboard Project.
# for the Linaro organization (http://linaro.org/)
#
# For more details see:
#   https://blueprints.launchpad.net/ubuntu/+spec/arm-m-validation-dashboard

"""
Public API for the ARM Validation Dashboard

This module provides API for working with storing and serializing
samples.

For more info see:
    - QualitativeSample
    - QuantitativeSample
"""


__author__ = "Zygmunt Krynicki <zygmunt.krynicki@linaro.org>"


import re


class _Sample(object):
    """
    Base class for QualitativeSample and QuantitativeSample classes.

    You can make samples that have no properties really
    >>> _Sample()
    <_Sample test_id:None>

    Usually samples will have a test_id for identifying which test case
    the result applies to. The test_id should use a reverse domain name
    naming convention.
    >>> _Sample(test_id='org.example.test1')
    <_Sample test_id:'org.example.test1'>
    """

    _TEST_ID_PATTERN = re.compile(
        "^([a-zA-Z_]+[a-zA-Z0-9_-]*)(\.[a-zA-Z_]+[a-zA-Z0-9_-]*)*$")

    __slots__ = ('_test_id', )

    def _get_test_id(self):
        return getattr(self, '_test_id', None)
    def _set_test_id(self, test_id):
        if test_id is not None and not self._TEST_ID_PATTERN.match(test_id):
            raise ValueError("Test id must be None or a string with reverse domain name")
        self._test_id = test_id

    test_id = property(_get_test_id, _set_test_id, None, """
            Unique identifier of the test case that produced this sample.

            In most primitive case the test_id may be None. This is
            useful for writing quick-and-easy log harvesters that just
            spot the fail/pass message in typical unit testing
            frameworks' logging code.

            Constructing bare _Sample instances like that is easy:
            >>> sample = _Sample()
            >>> sample.test_id is None
            True

            Extracting such samples is useful for detecting failures and
            showing pass/fail ratio/counts. Real code would use
            QualitativeSample and add a pass/fail status code.

            Most test cases will have a unique name so that the test can
            be tracked over time and across various different
            environments.

            Test ID uses reverse domain name scheme. Allowed characters
            in each domain component are:
                - alphanumeric characters: a-z, A-Z, 0-9
                - dash: -
                - underscore: _
            Valid test IDs match this pattern:
                ^([a-zA-Z_]+[a-zA-Z0-9_-]*)(\.[a-zA-Z_]+[a-zA-Z0-9_-]*)*$

            Some examples:

            >>> sample.test_id = 'org.linaro.boot.boot-time'
            >>> sample.test_id
            'org.linaro.boot.boot-time'
            >>> sample.test_id = \\
            ... 'com.some-library.SomeClass.test_some_method_with_a_long_name'
            >>> sample.test_id
            'com.some-library.SomeClass.test_some_method_with_a_long_name'

            Attempting to set invalid test_id raises ValueError with
            appropriate message.
            >>> sample.test_id = 'not a domain name'
            Traceback (most recent call last):
                ...
            ValueError: Test id must be None or a string with reverse domain name
            """)
    def __init__(self, **kwargs):
        for arg, value in kwargs.iteritems():
            setattr(self, arg, value)
    def __repr__(self):
        """
        Produce more-less human readable encoding of all fields.

        This function simply shows all fields in a simple format:
        >>> _Sample()
        <_Sample test_id:None>

        Note that implementation details such as slots and properties
        are hidden.  The produced string uses the public API to access
        all data. In this example the real test_id is stored in
        '_test_id' slot.
        >>> _Sample(test_id='foo.bar')
        <_Sample test_id:'foo.bar'>
        """
        slots = [slot[1:] if slot.startswith('_') else slot for slot in self.__slots__]
        fields = ["%s:%r" % (slot, getattr(self, slot)) for slot in slots]
        return "<%s %s>" % (self.__class__.__name__, " ".join(fields))


class QualitativeSample(_Sample):
    """
    Qualitative Sample class.
    Used to represent results for pass/fail test cases.

    Typical use case is a log analyzer that reads output from a unit
    test library or other simple format and constructs QualitativeSample
    instances based on simple property of the output (pass/fail marker).

    >>> sample = QualitativeSample('fail', 'org.ltp.some-test-case')
    >>> sample
    <QualitativeSample test_id:'org.ltp.some-test-case' test_result:'fail'>

    The two most important properties are test_id
    >>> sample.test_id
    'org.ltp.some-test-case'

    And test result
    >>> sample.test_result
    'fail'

    You should avoid using strings, they are defined like that only for the
    preferred json serialisation format. Each supported value of test_result
    is also available as an identifier.

    >>> sample.test_result == QualitativeSample.TEST_RESULT_FAIL
    True
    """
    __slots__ = ('_test_id', '_test_result')

    TEST_RESULT_PASS = "pass"
    TEST_RESULT_FAIL = "fail"
    _TEST_RESULTS = (TEST_RESULT_PASS, TEST_RESULT_FAIL)

    def _get_test_result(self):
        return self._test_result
    def _set_test_result(self, test_result):
        if test_result not in self._TEST_RESULTS:
            raise ValueError("Unsupported value of test result")
        self._test_result = test_result
    test_result = property(_get_test_result, _set_test_result, None, """
            Test result property.

            Holds one of several pre-defined test results. Note that
            Additional test result values will be registered as need
            arises. Client code should support unknown values
            gracefully.

            Samples from successful tests should use TEST_RESULT_PASS:
            >>> sample = QualitativeSample(QualitativeSample.TEST_RESULT_PASS)
            >>> sample.test_result
            'pass'

            Samples from failed tests should use TEST_RESULT_FAIL
            >>> sample = QualitativeSample(QualitativeSample.TEST_RESULT_FAIL)
            >>> sample.test_result
            'fail'

            Attempting to use unsupported values raises ValueError
            >>> QualitativeSample('this value should never be supported')
            Traceback (most recent call last):
                ...
            ValueError: Unsupported value of test result

            """)
    def __init__(self, test_result, test_id=None):
        """
        Initialize qualitative sample instance.

        The short form of this constructor sets only the test_result.
        >>> sample = QualitativeSample('fail')
        >>> sample.test_id
        >>> sample.test_result
        'fail'

        The longer form sets both test_id and test_result.
        >>> sample = QualitativeSample('pass', 'some-id')
        >>> sample.test_id
        'some-id'
        >>> sample.test_result
        'pass'
        """
        super(QualitativeSample, self).__init__(
                test_id=test_id, test_result=test_result)


def _test():
    """
    Test all docstrings.

    Usage: python sample.py [-v]
    """
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    _test()

