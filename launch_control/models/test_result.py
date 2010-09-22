# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of Launch Control.
#
# Launch Control is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# Launch Control is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Launch Control.  If not, see <http://www.gnu.org/licenses/>.

"""
Module with the TestResult model.
"""

from datetime import (datetime, timedelta)
from decimal import Decimal
from types import NoneType
import re

from launch_control.utils.json import PlainOldData


class TestResult(PlainOldData):
    """
    Model for representing test results - outcomes
    of running individual test cases of a particular test
    case during a particular test run.

    Available properties:
        - test_case_id: unique test identifier string (optional)
        - result: one of pre-defined strings
        - measurement: arbitrary numerical measurement
        - attributes: arbitrary key-value mapping for additional data.

    Some things are provided as convenient API end up in the
    attribute dictionary:
        - units: string representing units of the measurement
        - duration: duration of the test case
        - timestamp: time stamp as measured by the test case
        - message: arbitrary message, can be used to store
        errors and other output that the test spits out.
    """
    # Well-defined names for supported results
    RESULT_PASS = u"pass"
    RESULT_FAIL = u"fail"
    RESULT_SKIP = u"skip"
    RESULT_UNKNOWN = u"unknown"

    # Collection of valid results
    _VALID_RESULTS = (RESULT_PASS, RESULT_FAIL, RESULT_SKIP,
            RESULT_UNKNOWN)

    # Pattern for valid test case IDs
    _TEST_CASE_ID_PATTERN = re.compile(
        "^([a-zA-Z0-9_-]+)(\.[a-zA-Z0-9_-]+)*$")

    # Smallest supported timestamp:
    _MIN_TIMESTAMP = datetime(2010, 6, 1)

    __slots__ = ('_test_case_id', '_result', '_measurement',
            '_units', '_timestamp', '_duration', '_log_filename',
            '_log_lineno', '_message', 'attributes')

    def __init__(self, test_case_id, result, measurement=None,
            units=None, timestamp=None, duration=None, message=None,
            log_filename=None, log_lineno=None, attributes=None):
        """
        Initialize test result instance.
        """
        # Store None everywhere to make pylint happy
        self._test_case_id = None
        self._result = None
        self._measurement = None
        self._units = None
        self._timestmap = None
        self._duration = None
        self._message = None
        self._log_filename = None
        self._log_duration = None
        # Store real values through properties to validate input
        self.test_case_id = test_case_id
        self.result = result
        self.measurement = measurement
        self.units = units
        self.timestamp = timestamp
        self.duration = duration
        self.message = message
        self.log_filename = log_filename
        self.log_lineno = log_lineno
        # Store attributes as-is
        if attributes is None:
            attributes = {}
        self.attributes = attributes

    def _get_test_case_id(self):
        return self._test_case_id

    def _set_test_case_id(self, test_case_id):
        if test_case_id is not None \
                and not self._TEST_CASE_ID_PATTERN.match(test_case_id):
            raise ValueError("Test Case ID must be a string with reverse"
                            " domain name, or None")
        self._test_case_id = test_case_id

    test_case_id = property(_get_test_case_id, _set_test_case_id, None, """
            Unique identifier of the test case within the whole test.
            Note: fully qualified name that uniquly identifies a test
            case consists of the ID of the test and the ID of the test
            case. That is, there is no need to encode test ID in test
            case ID manually.

            In most primitive case the test case id may be None. This is
            useful for writing quick-and-easy log harvesters that just
            spot the fail/pass message in typical unit testing
            frameworks' logging code.

            Extracting such test results is useful for detecting
            failures and showing pass/fail ratio/counts.

            Most test cases will have a unique name so that the test can
            be tracked over time and across various different
            environments.

            Test case ID uses reverse domain name scheme. Allowed
            characters in each domain component are:
                - alphanumeric characters: a-z, A-Z, 0-9
                - dash: -
                - underscore: _
            Valid test case IDs match this pattern:
                ^([a-zA-Z_]+[a-zA-Z0-9_-]*)(\.[a-zA-Z_]+[a-zA-Z0-9_-]*)*$

            Some examples:
            >>> result = TestResult('boot-time', 'unknown', 10312)
            >>> result = TestResult('regressions.bug53262', 'pass')

            Note that TestRun instance with another ID (test ID) would
            be used as a container for each test results. The fully
            qualified test case name would then contain an ID of the
            test and the test case. A fully qualified ID might look like
            'org.gnu.gcc.regressions.bug53262'
            """)

    def _get_result(self):
        return self._result

    def _set_result(self, result):
        if not isinstance(result, basestring):
            raise TypeError("Test result must be a string or unicode object")
        if result not in self._VALID_RESULTS:
            raise ValueError("Unsupported value of test result")
        self._result = result

    result = property(_get_result, _set_result, None, """
            Test result property.

            Holds one of several pre-defined test results. Note that
            Additional test result values will be registered as need
            arises. Client code should support unknown values
            gracefully.

            Where possible you should avoid using strings for the
            test_result field, they are defined like that only for the
            preferred json serialisation format. Each supported value of
            test_result is also available as an identifier:
                RESULT_PASS,
                RESULT_FAIL,
                RESULT_SKIP and
                RESULT_UNKNOWN

            Successful tests should use RESULT_PASS:
            >>> result = TestResult('some-test-case',
            ...     TestResult.RESULT_PASS)

            Failed tests should use RESULT_FAIL:
            >>> result = TestResult('some-test-case',
            ...     TestResult.RESULT_FAIL)

            Skipped tests should use RESULT_SKIP:
            >>> result = TestResult('some-test-case',
            ...     TestResult.RESULT_SKIP)

            Results that cannot be categorized as any of the
            above should use RESULT_UNKNOWN.
            >>> result = TestResult('some-test-case',
            ...     TestResult.RESULT_UNKNOWN)

            The result name may be specified  as either plain or unicode
            string. The identity is retained but might be lost after
            serialization so don't count on it.
            >>> result.result = u'fail'
            >>> result.result = 'fail'

            The last result code (UNKNOWN) should be used for all
            benchmarks. Benchmarks can be assigned qualitative
            assessment from within the validation dashboard web
            application on a per-context basis. That is, when the test
            case code cannot determine pass or fail status by itself it
            should defer the decision to a human that will analyze the
            results.

            Attempting to use unsupported values raises ValueError:
            >>> result.result = 'this value should never be supported'
            Traceback (most recent call last):
                ...
            ValueError: Unsupported value of test result

            Using anything else raises TypeError:
            >>> result.result = 5
            Traceback (most recent call last):
                ...
            TypeError: Test result must be a string or unicode object
            """)

    def _get_measurement(self):
        return self._measurement

    def _set_measurement(self, value):
        valid_types = (int, long, float, Decimal, NoneType)
        if not isinstance(value, valid_types):
            raise TypeError("Measurement must be an int, long, float, Decimal or None")
        self._measurement = value

    measurement = property(_get_measurement, _set_measurement, None, """
            Measurement property.

            Measurement is the numeric quantity that is associated with
            a test result. The quantity describes a value of certain
            type. See the units property to know more.

            Measurement must be a number. Either int, long, float or Decimal:
            >>> result = TestResult('some-test', 'unknown')
            >>> result.measurement = 10
            >>> result.measurement = 10L
            >>> result.measurement = 10.0
            >>> result.measurement = Decimal('10.0')

            Attempting to use other values raises TypeError:
            >>> result.measurement = "great"
            Traceback (most recent call last):
                ...
            TypeError: Measurement must be an int, long, float, Decimal or None
            """)

    def _get_message(self):
        return self._message

    def _set_message(self, message):
        if message is not None and not isinstance(message, basestring):
            raise TypeError("Message must be None or a string")
        self._message = message

    message = property(_get_message, _set_message, None, """
            Message property.

            Message is used for storing arbitrary text that is related
            to the test result. This might be a human-readable fragment
            of the test output that explains a test failure, a
            backtrace, compiler error message or anything else that
            appropriate as context.

            By default test results don't have any messages.
            >>> result = TestResult('some-test-case', 'fail')
            >>> result.message is None
            True

            If you are writing a log analyser please include the
            relevant part of the log file that you used to deduce the
            test result in the message field.  This adds credibility to
            the system as data is 'traceable' back to the source.
            >>> result.message = "2010-06-15 12:49:41 Some test case: FAILED"
            """)

    def _get_timestamp(self):
        return self._timestamp

    def _set_timestamp(self, timestamp):
        if timestamp is not None and not isinstance(timestamp,
                datetime):
            raise TypeError("Timestamp must be None or datetime "
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
            >>> result = TestResult('some-test-case', 'fail')
            >>> result.timestamp is None
            True

            You can set the timestamp to almost any datetime instance.
            The same type is used inside the django-based server side
            dashboard application.
            >>> result.timestamp = datetime(2010, 6, 18, 21, 06, 41)

            Do not store the timestamp unless you are sure that the
            device under test has accurate real-time clock settings.
            Test results with timestamp predating 1st of June 2010 will
            raise ValueError exception:
            >>> result.timestamp = datetime(2010, 5, 31, 23, 59, 59)
            Traceback (most recent call last):
                ...
            ValueError: Timestamp value predates 1st of June 2010

            There is a secondary field in the TestRun model that you can
            use to indicate if the device had accurate time while the
            test was performed.
            """)

    def _get_duration(self):
        return self._duration

    def _set_duration(self, duration):
        if duration is not None and not isinstance(duration, timedelta):
            raise TypeError("Duration must be None or timedelta "
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
            samples. When measured it should be a timedelta
            instance between the end and the start of the test.

            Note that the start of the test (stored in timestamp
            property) is independent from this value. Duration can be
            measured even on devices where the real time clock is not
            reliable and contains inaccurate data.

            By default duration is not set:
            >>> sample = TestResult('some-test-case', 'fail')
            >>> sample.duration is None
            True

            Only timedelta values are supported:
            >>> sample.duration = timedelta(seconds=10)

            All other types raise TypeError:
            >>> sample.duration = 10
            Traceback (most recent call last):
                ...
            TypeError: Duration must be None or timedelta instance

            Last restriction is that duration cannot be negative:
            >>> sample.duration = timedelta(seconds=-1)
            Traceback (most recent call last):
                ...
            ValueError: Duration cannot be negative
            """)

    def _get_units(self):
        return self._units

    def _set_units(self, units):
        self._units = units

    units = property(_get_units, _set_units, None, """
            Units property.

            Units add semantics to measurement values. This is _not_ a
            purely presentational property. While the dashboard UI will
            display it on graphs it is also used for deciding if two
            data series can be displayed at once on the same graph.

            Care must be taken to ensure that consistent naming theme is
            applied to all units.
            """)

    def _get_log_filename(self):
        return self._log_filename

    def _set_log_filename(self, log_filename):
        self._log_filename = log_filename

    log_filename = property(_get_log_filename, _set_log_filename, None,
            "Log file name")

    def _get_log_lineno(self):
        return self._log_lineno

    def _set_log_lineno(self, log_lineno):
        self._log_lineno = log_lineno

    log_lineno = property(_get_log_lineno, _set_log_lineno, None,
            "Log file line number")

    def set_origin(self, filename, lineno):
        """
        Set the origin of this test result to the attachment `file_name'
        line `lineno'. Documents start with line 1.
        """
        self.log_filename = filename
        self.log_lineno = lineno

    @classmethod
    def get_json_attr_types(self):
        return {'timestamp': datetime,
                'duration': timedelta,
                'measurement': Decimal}

    @classmethod
    def from_json(cls, json_doc):
        """
        Custom from_json() that makes test_case_id default to None This
        is useful to keep the __init__() API stable (it always requires
        two arguments) and allow test result loaded from JSON text have
        this argument optional
        """
        if "test_case_id" not in json_doc:
            json_doc['test_case_id'] = None
        return super(TestResult, cls).from_json(json_doc)
