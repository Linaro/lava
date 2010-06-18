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
import types
import datetime

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

    class _Dummy(object):
        """ Dummy values for unit testing """
        test_id = "some.test.id"

    def _get_test_id(self):
        return self._test_id

    def _set_test_id(self, test_id):
        if test_id is not None and not self._TEST_ID_PATTERN.match(test_id):
            raise ValueError("Test id must be None or a string with reverse "
                    "domain name")
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

    def __init__(self, test_id=None, **kwargs):
        self._test_id = test_id
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
        slots = [s[1:] if s.startswith('_') else s for s in self.__slots__]
        fields = ["%s:%r" % (slot, getattr(self, slot)) for slot in slots]
        return "<%s %s>" % (self.__class__.__name__, " ".join(fields))


class QualitativeSample(_Sample):
    """
    Qualitative Sample class. Used to represent results for pass/fail
    test cases.

    Available fields:
        - test_id: unique test identifier string (optional)
        - test_result: one of pre-defined strings
        - message: arbitrary string (optional)
        - timestamp: datetime.datetime() of measurement (optional)
        - duration: positive datetime.timedelta() of the measurement (optional)

    Typical use case is a log analyzer that reads output from a unit
    test library or other simple format and constructs QualitativeSample
    instances based on simple property of the output (pass/fail marker).

    The two most important properties are test_id and test_result
    >>> sample = QualitativeSample('fail', 'org.ltp.some-test-case')
    >>> sample.test_id
    'org.ltp.some-test-case'
    >>> sample.test_result
    'fail'

    You should avoid using strings for the test_result field, they are
    defined like that only for the preferred json serialisation format.
    Each supported value of test_result is also available as an
    identifier.
    >>> sample.test_result == QualitativeSample.TEST_RESULT_FAIL
    True

    Message is used for storing arbitrary log result. By default
    samples don't have any messages.
    >>> sample.message is None
    True

    If you are writing a log analyser please include the relevant part
    of the log file that you used to deduce the test result in the
    message field.  This adds credibility to the system as data is
    'tracable'.
    >>> sample.message = "2010-06-15 12:49:41 Some test case: FAILED"

    The timestamp field can be used to store a timestamp of the
    measurement. The dashboard UI can use this in some cases. Again by
    default timestamp is None.
    >>> sample.timestamp is None
    True

    To continue with the previous example, the log parser could harvest
    the timestamp from the log file and add it to the test result.
    >>> import datetime
    >>> sample.timestamp = datetime.datetime(2010, 6, 15, 12, 49, 41)

    TODO: describe the duration field and its connection to the
    timestamp field.
    """
    __slots__ = _Sample.__slots__ + ('_test_result', '_message', '_timestamp',
            '_duration')

    class _Dummy(_Sample._Dummy):
        """ Dummy values for unit testing """
        import datetime
        test_result = "pass"
        message = "Test successful"
        timestamp = datetime.datetime(2010, 06, 16, 18, 16, 23)
        duration = datetime.timedelta(seconds=15)

    TEST_RESULT_PASS = "pass"
    TEST_RESULT_FAIL = "fail"
    TEST_RESULT_SKIP = "skip"
    TEST_RESULT_CRASH = "crash"
    _TEST_RESULTS = (
            TEST_RESULT_PASS, TEST_RESULT_FAIL,
            TEST_RESULT_SKIP, TEST_RESULT_CRASH)

    def _get_test_result(self):
        return self._test_result

    def _set_test_result(self, test_result):
        if not isinstance(test_result, types.StringTypes):
            raise TypeError("Test result must be a string or unicode object")
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
    def _get_message(self):
        return self._message

    def _set_message(self, message):
        if not isinstance(message, (types.NoneType, ) + types.StringTypes):
            raise TypeError("Message must be None or a string")
        self._message = message

    message = property(_get_message, _set_message, None, """
            Message property.
            """)

    def _get_timestamp(self):
        return self._timestamp

    def _set_timestamp(self, timestamp):
        if timestamp is not None and not isinstance(timestamp,
                datetime.datetime):
            raise TypeError("Timestamp must be None or datetime.datetime() "
                    "instance")
        self._timestamp = timestamp

    timestamp = property(_get_timestamp, _set_timestamp, None, """
            Timestamp property.
            """)

    def _get_duration(self):
        return self._duration

    def _set_duration(self, duration):
        if duration is not None and not isinstance(duration,
                datetime.timedelta):
            raise TypeError("duration must be None or datetime.timedelta() "
                    "instance")
        if duration is not None and duration.days < 0:
            raise ValueError("duration cannot be negative")
        self._duration = duration

    duration = property(_get_duration, _set_duration, None, """
            Duration property.
            """)

    def __init__(self, test_result, test_id=None, message=None,
            timestamp=None, duration=None):
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

        Since all other arguments are optional. You can use
        them to specify the message and the timestamp.
        """
        super(QualitativeSample, self).__init__(
                test_id=test_id, test_result=test_result,
                message=message, timestamp=timestamp, duration=duration)


def _test():
    """
    Test all docstrings.

    Usage: python sample.py [-v]
    """
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    _test()

