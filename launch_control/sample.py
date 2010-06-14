# This file is part of the ARM Validation Dashboard Project.
# for the Linaro organization (http://linaro.org/)
#
#
# For more details see:
#   https://blueprints.launchpad.net/ubuntu/+spec/arm-m-validation-dashboard
#
# ARM Validation Dashboard is free software; you can redistribute it
# and/or modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either version
# 2.1 of the License, or (at your option) any later version.
#
# ARM Validation Dashboard is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with ARM Validation Dashboard; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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

    >>> _Sample()
    <_Sample test_id:None>
    >>> _Sample(test_id='foo.bar')
    <_Sample test_id:'foo.bar'>
    >>> _Sample(test_id='foo.bar.froz')
    <_Sample test_id:'foo.bar.froz'>
    """
    _TEST_ID_PATTERN = re.compile(
        "^([a-zA-Z_]+[a-zA-Z0-9_-]*)(\.[a-zA-Z_]+[a-zA-Z0-9_-]*)*$")
    __slots__ = ('_test_id', )

    def _get_test_id(self):
        """
        >>> s = _Sample()
        >>> s.test_id is None
        True
        """
        return getattr(self, '_test_id', None)
    def _set_test_id(self, test_id):
        """
        >>> s = _Sample(test_id='com.something.sometest')
        >>> s.test_id
        'com.something.sometest'
        >>> s.test_id = 'invalid name'
        Traceback (most recent call last):
            ...
        ValueError: Test id must be None or a string with reverse domain name
        """
        if test_id is not None and not self._TEST_ID_PATTERN.match(test_id):
            raise ValueError("Test id must be None or a string with reverse domain name")
        self._test_id = test_id

    test_id = property(_get_test_id, _set_test_id, None, """
            Unique identifier of the test case that produced this sample.
            May be None

            Test ID is uses reverse domain name scheme, for example:
                - org.linaro.boot.boot-time
                - com.some-library.SomeClass.test_some_method_with_a_long_name

            Allowed characters in each domain component are:
                - alphanumeric characters: a-z, A-Z, 0-9
                - dash: -
                - underscore: _

            >>> sample = _Sample()
            >>> sample
            <_Sample test_id:None>
            >>> sample.test_id is None
            True
            >>> sample.test_id = 'some.value'
            >>> sample.test_id
            'some.value'
            """)
    def __init__(self, **kwargs):
        for arg, value in kwargs.iteritems():
            setattr(self, arg, value)
    def __repr__(self):
        """
        Produce more-less human readable encoding of all fields.

        >>> _Sample()
        <_Sample test_id:None>
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

    Available fields:
    - test_id: unique test identifier string (may be None)
    - test_result: either 'pass' or 'fail'

    >>> QualitativeSample('fail', 'org.ltp.some-test-case')
    <QualitativeSample test_id:'org.ltp.some-test-case' test_result:'fail'>

    >>> QualitativeSample('pass')
    <QualitativeSample test_id:None test_result:'pass'>
    """
    __slots__ = ('_test_id', '_test_result')

    TEST_RESULT_PASS = "pass"
    TEST_RESULT_FAIL = "fail"
    _TEST_RESULTS = (TEST_RESULT_PASS, TEST_RESULT_FAIL)

    def _get_test_result(self):
        """
        >>> QualitativeSample(QualitativeSample.TEST_RESULT_PASS)
        <QualitativeSample test_id:None test_result:'pass'>
        >>> QualitativeSample(QualitativeSample.TEST_RESULT_FAIL)
        <QualitativeSample test_id:None test_result:'fail'>
        """
        return self._test_result
    def _set_test_result(self, test_result):
        """
        >>> QualitativeSample('this value should never be supported')
        Traceback (most recent call last):
            ...
        ValueError: Unsupported value of test result
        """
        if test_result not in self._TEST_RESULTS:
            raise ValueError("Unsupported value of test result")
        self._test_result = test_result
    test_result = property(_get_test_result, _set_test_result, None, """
            Test result property.

            Holds one of several pre-defined test result values.
            Supported values:
                - TEST_RESULT_PASS ('pass')
                - TEST_RESULT_FAIL ('fail')

            Additional test result values will be registered as need arises.
            Client code should support unknown values gracefully.

            >>> sample = QualitativeSample('pass')
            >>> sample.test_result
            'pass'
            >>> sample.test_result == QualitativeSample.TEST_RESULT_PASS
            True
            >>> sample.test_result = 'fail'
            >>> sample.test_result
            'fail'
            >>> sample.test_result == QualitativeSample.TEST_RESULT_FAIL
            True
            """)
    def __init__(self, test_result, test_id=None):
        """
        Initialize qualitative sample.
        Arguments:
            `test_result`: pass/fail result of the test case
            `test_id`: unique name of the test
        >>> QualitativeSample('fail')
        <QualitativeSample test_id:None test_result:'fail'>
        >>> QualitativeSample('pass')
        <QualitativeSample test_id:None test_result:'pass'>
        >>> QualitativeSample('pass', 'some-id')
        <QualitativeSample test_id:'some-id' test_result:'pass'>
        """
        super(QualitativeSample, self).__init__(
                test_id=test_id, test_result=test_result)


def _test():
    """
    Test all docstrings
    """
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    _test()

