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

    def __init__(self, test_id=None):
        # Store `None' value as-is
        self._test_id = None
        # Store real value with validation
        self.test_id = test_id

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
        - test_result: one of pre-defined strings
        - test_id: unique test identifier string (optional)
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

    See the documentation of each property for more information.
    """
    __slots__ = _Sample.__slots__ + ('_test_result', '_message',
            '_timestamp', '_duration')

    TEST_RESULT_PASS = "pass"
    TEST_RESULT_FAIL = "fail"
    TEST_RESULT_SKIP = "skip"
    TEST_RESULT_UNKNOWN = "unknown"
    _TEST_RESULTS = (
            TEST_RESULT_PASS, TEST_RESULT_FAIL,
            TEST_RESULT_SKIP, TEST_RESULT_UNKNOWN)

    # Smallest supported timestamp:
    _MIN_TIMESTAMP = datetime.datetime(2010, 6, 1)

    def _get_test_result(self):
        return self._test_result

    def _set_test_result(self, test_result):
        if not isinstance(test_result, basestring):
            raise TypeError("Test result must be a string or unicode object")
        if test_result not in self._TEST_RESULTS:
            raise ValueError("Unsupported value of test result")
        self._test_result = str(test_result)

    test_result = property(_get_test_result, _set_test_result, None, """
            Test result property.

            Holds one of several pre-defined test results. Note that
            Additional test result values will be registered as need
            arises. Client code should support unknown values
            gracefully.

            Where possible you should avoid using strings for the
            test_result field, they are defined like that only for the
            preferred json serialisation format. Each supported value of
            test_result is also available as an identifier.
            >>> sample = QualitativeSample('fail', 'org.ltp.some-test-case')
            >>> sample.test_result == QualitativeSample.TEST_RESULT_FAIL
            True

            Samples from successful tests should use TEST_RESULT_PASS:
            >>> sample = QualitativeSample(
            ...     QualitativeSample.TEST_RESULT_PASS)
            >>> sample.test_result
            'pass'

            Samples from failed tests should use TEST_RESULT_FAIL:
            >>> sample = QualitativeSample(
            ...     QualitativeSample.TEST_RESULT_FAIL)
            >>> sample.test_result
            'fail'

            Samples from tests that were skipped should use TEST_RESULT_SKIP:
            >>> sample = QualitativeSample(
            ...     QualitativeSample.TEST_RESULT_SKIP)
            >>> sample.test_result
            'skip'

            Samples from tests that failed for any other reason should
            use TEST_RESULT_UNKNOWN
            >>> sample = QualitativeSample(
            ...     QualitativeSample.TEST_RESULT_UNKNOWN)
            >>> sample.test_result
            'unknown'

            Valid types are strings (either plain or unicode):
            >>> sample.test_result = u'fail'
            >>> sample.test_result = 'fail'

            Everything else raises TypeError:
            >>> sample.test_result = 5
            Traceback (most recent call last):
                ...
            TypeError: Test result must be a string or unicode object

            Attempting to use unsupported values raises ValueError:
            >>> sample.test_result = 'this value should never be supported'
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

            Message is used for storing arbitrary log result. This
            message is usually provided by test case code.

            By default samples don't have any messages.
            >>> sample = QualitativeSample('fail', 'org.ltp.some-test-case')
            >>> sample.message is None
            True

            If you are writing a log analyser please include the
            relevant part of the log file that you used to deduce the
            test result in the message field.  This adds credibility to
            the system as data is 'traceable' back to the source.
            >>> sample.message = "2010-06-15 12:49:41 Some test case: FAILED"
            """)

    def _get_timestamp(self):
        return self._timestamp

    def _set_timestamp(self, timestamp):
        if timestamp is not None and not isinstance(timestamp,
                datetime.datetime):
            raise TypeError("Timestamp must be None or datetime.datetime() "
                    "instance")
        if timestamp is not None and timestamp < self._MIN_TIMESTAMP:
            raise ValueError("Timestamp value predates 1st of June 2010")
        self._timestamp = timestamp

    timestamp = property(_get_timestamp, _set_timestamp, None,
            """
            Timestamp property.

            The timestamp can store the date and time of the start of
            sample measurement. The dashboard UI will display this
            information when possible. Timestamp works together with the
            duration property.

            By default timestamp is not set:
            >>> sample = QualitativeSample('fail', 'org.ltp.some-test-case')
            >>> sample.timestamp is None
            True

            You can set the timestamp to almost any datetime.datetime()
            instance. The same type is used inside the django-based
            server side dashboard application.
            >>> import datetime
            >>> sample.timestamp = datetime.datetime(2010, 6, 18, 21, 06, 41)

            Do not store the timestamp unless you are sure that the
            device under test has accurate real-time clock settings.
            Samples with timestamp predating 1st of June 2010 will raise
            ValueError exception:
            >>> sample.timestamp = datetime.datetime(2010, 5, 31, 23, 59, 59)
            Traceback (most recent call last):
                ...
            ValueError: Timestamp value predates 1st of June 2010
            """)

    def _get_duration(self):
        return self._duration

    def _set_duration(self, duration):
        if duration is not None and not isinstance(duration,
                datetime.timedelta):
            raise TypeError("Duration must be None or datetime.timedelta() "
                    "instance")
        if duration is not None and duration.days < 0:
            raise ValueError("Duration cannot be negative")
        self._duration = duration

    duration = property(_get_duration, _set_duration, None,
            """
            Duration property.

            The duration property is designed to hold the duration of
            the test that produced this sample. This property is
            optional and does not necessarily makes sense for all
            samples. When measured it should be a datetime.timedelta()
            instance between the end and the start of the test.

            Note that the start of the test (stored in timestamp
            property) is independent from this value. Duration can be
            measured even on devices where the real time clock is not
            reliable and contains inaccurate data.

            By default duration is not set:
            >>> sample = QualitativeSample('fail')
            >>> sample.duration is None
            True

            Only datetime.timedelta() values are supported:
            >>> sample.duration = datetime.timedelta(seconds=10)

            All other types raise TypeError:
            >>> sample.duration = 10
            Traceback (most recent call last):
                ...
            TypeError: Duration must be None or datetime.timedelta() instance

            Last restriction is that duration cannot be negative:
            >>> sample.duration = datetime.timedelta(seconds=-1)
            Traceback (most recent call last):
                ...
            ValueError: Duration cannot be negative
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

        All other arguments are optional. You can use them to specify
        the message, timestamp and duration.
        """
        # store `None' value as-is
        self._test_result = None
        self._message = None
        self._timestamp = None
        self._duration = None
        # call super constructor to store test_id
        super(QualitativeSample, self).__init__(test_id)
        # store real values with validation
        self.test_result = test_result
        self.message = message
        self.timestamp = timestamp
        self.duration = duration


def _test():
    """
    Test all docstrings.

    Usage: python sample.py [-v]
    """
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    _test()

