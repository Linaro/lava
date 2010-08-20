"""
Test cases for launch_control.sample module
"""
from unittest import TestCase
import datetime

from launch_control.utils.call_helper import ObjectFactory
from launch_control.utils.json import (
        ClassRegistry,
        PluggableJSONDecoder,
        PluggableJSONEncoder,
        json)
from launch_control.utils.json.proxies.datetime import datetime_proxy
from launch_control.utils.json.proxies.decimal import DecimalProxy
from launch_control.utils.json.proxies.timedelta import timedelta_proxy
from launch_control.utils.json.proxies.uuid import UUIDProxy
from launch_control.sample import (
        _Sample,
        QualitativeSample,
        QuantitativeSample)


class _Dummy_Sample(object):
    """ Dummy values for unit testing _Sample"""
    test_id = "some.test.id"


class _SampleTestCase(TestCase):
    """ Test case with _Sample instance and _Sample factory"""

    def _get_factory(self):
        """ Factory for making dummy _Sample objects """
        return ObjectFactory(_Sample, _Dummy_Sample)

    def setUp(self):
        """
        unittest.TestCase.setUp method

        Prepares .factory and .sample
        """
        super(_SampleTestCase, self).setUp()
        self.factory = self._get_factory()
        self.sample = self.factory()


class _SampleConstruction(_SampleTestCase):
    """
    Check construction behavior for _Sample or its sub-classes.

    This test case uses ObjectFactory that makes instances of _Sample or
    its sub-classes (in sub-classes of _SampleConstruction).

    Each particular test checks for certain constructor property:
        - certain argument having concrete default,
        - certain argument being copied to internal field

    Those tests use the fact that ObjectFactory (a simple facility that
    makes objects and uses a pool of dummy values for non-default
    arguments) will fill only non-default arguments with dummy values.

    A test that wants to see if test_id default is 'foo' could simply
    make an instance with test_id equalt to ObjectFactory.DEFAULT_VALUE
    and inspect the test_id of the instantiated object.

    This has the advantage of working well with sub-classes.
    If a sub-class changes the constructor it has to update just the
    unit tests that are no longer valid (like default being changed, new
    arguments being added, etc). The rest will just work without the
    extra effort.
    """

    def test_construction_validates_test_id(self):
        """ Validation works inside the constructor """
        self.assertRaises(ValueError, self.factory, test_id='')

    def test_constructor_test_id_default_value(self):
        """ Argument test_id defaults to None """
        sample = self.factory(test_id=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.test_id, None)

    def test_constructor_sets_test_id(self):
        """ Argument test_id is stored correctly """
        value = self.factory.dummy.test_id
        sample = self.factory(test_id=value)
        self.assertEqual(sample.test_id, value)

    def test_constructor_test_id_can_be_None(self):
        sample = self.factory(test_id=None)
        self.assertEqual(sample.test_id, None)


class _SampleGoodInput(_SampleTestCase):
    """ Using valid values for all attributes must work correctly """

    def test_test_id_can_be_a_single_word(self):
        self.sample.test_id = 'word'
        self.assertEqual(self.sample.test_id, 'word')

    def test_test_id_can_be_a_dotted_sentence(self):
        test_id = 'dotted.sentence.that.is.not.a.domain.name'
        self.sample.test_id = test_id
        self.assertEqual(self.sample.test_id, test_id)

    def test_test_id_can_contain_hypens(self):
        self.sample.test_id = 'hypen-okay'
        self.assertEqual(self.sample.test_id, 'hypen-okay')

    def test_test_id_can_contain_underscores(self):
        self.sample.test_id = 'underscore_okay'
        self.assertEqual(self.sample.test_id, 'underscore_okay')

    def test_test_id_can_be_uppercase(self):
        self.sample.test_id = 'UPPERCASE'
        self.assertEqual(self.sample.test_id, 'UPPERCASE')


class _SampleBadInput(_SampleTestCase):
    """ Using invalid values for any attribute must raise exceptions """

    def test_test_id_cannot_have_spaces(self):
        self.assertRaises(ValueError, setattr, self.sample, 'test_id',
                'something that does not look like a domain name')

    def test_test_id_cannot_be_empty(self):
        self.assertRaises(ValueError, setattr, self.sample, 'test_id', '')


class _SampleJSONSupport(TestCase):

    def setUp(self):
        self.registry = ClassRegistry()
        self.registry.register(_Sample)
        self.reference_sample = _Sample(
                test_id = "org.example.test-id")
        self.reference_serialization = '{"__class__": "_Sample", ' \
                '"test_id": "org.example.test-id"}'

    def test_to_json(self):
        serialization = json.dumps(self.reference_sample,
                cls=PluggableJSONEncoder,
                registry=self.registry,
                sort_keys=True)
        self.assertEqual(serialization, self.reference_serialization)

    def test_from_json(self):
        sample = json.loads(self.reference_serialization,
                cls=PluggableJSONDecoder,
                registry=self.registry)
        self.assertEqual(sample, self.reference_sample)


class QualitativeSampleClassProperties(TestCase):
    """"Check for properties of QualitativeSample class"""

    def test_TEST_RESULT_PASS_is_pass(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_PASS, 'pass')

    def test_TEST_RESULT_FAIL_is_fail(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_FAIL, 'fail')

    def test_TEST_RESULT_SKIP_is_skip(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_SKIP, 'skip')

    def test_TEST_RESULT_UNKNOWN_is_unknown(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_UNKNOWN, 'unknown')


class _DummyQualitativeSample(_Dummy_Sample):
    """ Dummy values for unit testing QualitativeSample """
    test_result = "pass"
    message = "Test successful"
    timestamp = datetime.datetime(2010, 06, 16, 18, 16, 23)
    duration = datetime.timedelta(seconds=15)


class QualitativeSampleTestCase(_SampleTestCase):
    """
    Test case with QualitativeSample instance and QualitativeSample
    factory
    """
    def _get_factory(self):
        """ Factory for making dummy QualitativeSample objects """
        return ObjectFactory(QualitativeSample, _DummyQualitativeSample)


class QualitativeSampleConstruction(QualitativeSampleTestCase,
        _SampleConstruction):
    """
    Check construction behavior for QualitativeSample.

    This test case inherits all tests from _SampleConstruction test
    case. Only new or altered arguments are changed. The rest retains
    their meaning from the base class.
    """

    def test_constructor_requires_arguments(self):
        """ At least one argument is required: test_result """
        self.assertRaises(TypeError, QualitativeSample)

    def test_constructor_sets_test_result(self):
        """ Check that all test results can be used """
        sample = self.factory(
                test_result=QualitativeSample.TEST_RESULT_FAIL)
        self.assertEqual(sample.test_result, 'fail')
        sample = self.factory(
                test_result=QualitativeSample.TEST_RESULT_PASS)
        self.assertEqual(sample.test_result, 'pass')
        sample = self.factory(
                test_result=QualitativeSample.TEST_RESULT_SKIP)
        self.assertEqual(sample.test_result, 'skip')
        sample = self.factory(
                test_result=QualitativeSample.TEST_RESULT_UNKNOWN)
        self.assertEqual(sample.test_result, 'unknown')

    def test_constructor_message_default_value(self):
        """ Argument message defaults to None """
        sample = self.factory(message=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.message, None)

    def test_constructor_sets_bytestring_message(self):
        """ Argument message is stored correctly (for byte strings) """
        sample = self.factory(message='foobar')
        self.assertEqual(sample.message, 'foobar')

    def test_constructor_sets_unicode_message(self):
        """
        Argument message is stored correctly (for unicode strings)
        """
        sample = self.factory(message=u'foobar')
        self.assertEqual(sample.message, u'foobar')

    def test_constructor_timestamp_default_value(self):
        """ Argument timestamp defaults to None """
        sample = self.factory(timestamp=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.timestamp, None)

    def test_constructor_sets_timestamp(self):
        """ Argument timestamp is stored correctly """
        value = self.factory.dummy.timestamp
        sample = self.factory(timestamp=value)
        self.assertEqual(sample.timestamp, value)

    def test_constructor_duration_default_value(self):
        """ Argument duration defaults to None """
        sample = self.factory(duration=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.duration, None)

    def test_constructor_sets_duration(self):
        """ Argument duration is stored correctly """
        value = self.factory.dummy.duration
        sample = self.factory(duration=value)
        self.assertEqual(sample.duration, value)


class QualitativeSampleGoodInput(QualitativeSampleTestCase, _SampleGoodInput):
    """ Using valid values for all attributes must work correctly """

    def test_test_result_is_stored_as_plain_string(self):
        self.sample.test_result = u'pass'
        self.assertEqual(self.sample.test_result, 'pass')

    def test_test_result_can_be_set_to_pass(self):
        self.sample.test_result = QualitativeSample.TEST_RESULT_PASS
        self.assertEqual(self.sample.test_result, 'pass')

    def test_test_result_can_be_set_to_fail(self):
        self.sample.test_result = QualitativeSample.TEST_RESULT_FAIL
        self.assertEqual(self.sample.test_result, 'fail')

    def test_test_result_can_be_set_to_skip(self):
        self.sample.test_result = QualitativeSample.TEST_RESULT_SKIP
        self.assertEqual(self.sample.test_result, 'skip')

    def test_test_result_can_be_set_to_unknown(self):
        self.sample.test_result = QualitativeSample.TEST_RESULT_UNKNOWN
        self.assertEqual(self.sample.test_result, 'unknown')

    def test_message_can_be_a_string(self):
        self.sample.message = 'foo'
        self.assertEqual(self.sample.message, 'foo')

    def test_message_can_be_a_unicode_string(self):
        self.sample.message = u'foo'
        self.assertEqual(self.sample.message, 'foo')

    def test_message_can_be_None(self):
        self.sample.message = None
        self.assertEqual(self.sample.message, None)

    def test_timestamp_can_be_None(self):
        self.sample.timestamp = None
        self.assertEqual(self.sample.timestamp, None)

    def test_timestamp_can_be_a_datetime(self):
        timestamp = datetime.datetime(2010, 6, 1, 15, 00)
        self.sample.timestamp = timestamp
        self.assertEqual(self.sample.timestamp, timestamp)

    def test_duration_can_be_None(self):
        self.sample.duration = None
        self.assertEqual(self.sample.duration, None)

    def test_duration_can_be_timedelta(self):
        duration = datetime.timedelta(minutes=2, seconds=5)
        self.sample.duration = duration
        self.assertEqual(self.sample.duration, duration)


class QualitativeSampleJSONSupport(_SampleJSONSupport):

    def setUp(self):
        super(QualitativeSampleJSONSupport, self).setUp()
        self.registry.register(QualitativeSample)
        self.registry.register_proxy(datetime.datetime, datetime_proxy)
        self.registry.register_proxy(datetime.timedelta, timedelta_proxy)
        self.reference_sample = QualitativeSample(
                test_result = QualitativeSample.TEST_RESULT_PASS,
                test_id = "org.example.test-id",
                message = "Test successful",
                timestamp = datetime.datetime(2010, 06, 24, 13, 43, 57),
                duration = datetime.timedelta(days=0, minutes=7, seconds=12))
        self.reference_serialization = '{"__class__": "QualitativeSample", ' \
                '"duration": "0d 432s 0us", "message": "Test successful", ' \
                '"test_id": "org.example.test-id", "test_result": "pass", ' \
                '"timestamp": "2010-06-24T13:43:57Z"}'


class QualitativeSampleBadInput(QualitativeSampleTestCase, _SampleBadInput):
    """ Using invalid values for any attribute must raise exceptions """

    def test_test_result_cannot_be_None(self):
        self.assertRaises(TypeError, setattr, self.sample,
                'test_result', None)

    def test_test_result_cannot_be_empty(self):
        self.assertRaises(ValueError, setattr, self.sample, 'test_result', '')

    def test_test_result_cannot_be_arbitrary(self):
        self.assertRaises(ValueError, setattr, self.sample,
                'test_result', 'bonk')
        self.assertRaises(ValueError, setattr, self.sample,
                'test_result', 'puff')

    def test_message_cannot_be_non_string(self):
        self.assertRaises(TypeError, setattr, self.sample, 'message', 123)
        self.assertRaises(TypeError, setattr, self.sample, 'message', 123.5)
        self.assertRaises(TypeError, setattr, self.sample, 'message', True)
        self.assertRaises(TypeError, setattr, self.sample, 'message', {})
        self.assertRaises(TypeError, setattr, self.sample, 'message', [])

    def test_timestamp_cannot_be_non_datetime(self):
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', 0)
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', 152.5)
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', -152.5)
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', False)
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', 'booo')
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', '')
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', {})
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', [])

    def test_timestamp_cannot_preceed_june_2010(self):
        timestamp = datetime.datetime(2010, 6, 1)
        timestamp -= datetime.datetime.resolution # 1 micro second
        self.assertRaises(ValueError, setattr, self.sample, 'timestamp',
                timestamp)

    def test_duration_cannot_be_negative(self):
        duration = datetime.timedelta(microseconds=-1)
        self.assertRaises(ValueError, setattr, self.sample, 'duration',
                duration)

    def test_duration_cannot_be_non_datetime(self):
        self.assertRaises(TypeError, setattr, self.sample, 'duration', 0)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', 152.5)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', -152.5)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', False)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', 'booo')
        self.assertRaises(TypeError, setattr, self.sample, 'duration', '')
        self.assertRaises(TypeError, setattr, self.sample, 'duration', {})
        self.assertRaises(TypeError, setattr, self.sample, 'duration', [])


class _DummyQuantitativeSample(_DummyQualitativeSample):
    """ Dummy values for unit testing QualitativeSample """
    measurement = 100
    units = 'MiB/s'


class QuantitativeSampleTestCase(QualitativeSampleTestCase):
    """
    Test case with QuantitativeSample instance and QuantitativeSample
    factory
    """
    def _get_factory(self):
        """ Factory for making dummy QuantitativeSample objects """
        return ObjectFactory(QuantitativeSample, _DummyQuantitativeSample)


class QuantitativeSampleConstruction(
        QuantitativeSampleTestCase, _SampleConstruction):
    """
    Check construction behavior for QuantitativeSample.

    This test case uses ObjectFactory that makes instances of
    QuantitativeSample.
    """
    # test_id property
    def test_constructor_test_id_default_value(self):
        """ There is no default value for test_id """
        self.assertRaises(ValueError, self.factory,
                test_id=ObjectFactory.DEFAULT_VALUE)

    def test_constructor_test_id_can_be_None(self):
        """ Constructor allows for None test_id"""
        self.assertRaises(ValueError, self.factory, test_id=None)

    # measurement property
    def test_constructor_measurement_default_value(self):
        """ There is no default value for measurement """
        self.assertRaises(ValueError, self.factory,
                measurement=ObjectFactory.DEFAULT_VALUE)

    def test_constructor_sets_measurement(self):
        """ Constructor copies measurement property """
        value = self.factory.dummy.measurement
        sample = self.factory(measurement=value)
        self.assertEqual(sample.measurement, value)

    def test_constructor_restricts_None_measurement(self):
        """ Constructor restricts None value of measurement to samples
        with failing test_result. Value error is raised otherwise """
        self.assertRaises(ValueError, self.factory, measurement=None,
                test_result=QualitativeSample.TEST_RESULT_PASS)
        for test_result in (
                QualitativeSample.TEST_RESULT_FAIL,
                QualitativeSample.TEST_RESULT_SKIP,
                QualitativeSample.TEST_RESULT_UNKNOWN):
            sample = self.factory(
                    measurement=None,
                    test_result=test_result)
            self.assertEqual(sample.measurement, None)
            self.assertEqual(sample.test_result, test_result)

    # units property
    def test_constructor_units_default_value(self):
        """ Default value for units is None """
        sample = self.factory(units=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.units, None)

    def test_constructor_sets_units(self):
        """ Constructor copies units property """
        value = self.factory.dummy.units
        sample = self.factory(units=value)
        self.assertEqual(sample.units, value)


class QuantitativeSampleGoodInput(QuantitativeSampleTestCase,
        QualitativeSampleGoodInput):
    """ Using valid values for all attributes must work correctly """


class QuantitativeSampleBadInput(QuantitativeSampleTestCase,
        QualitativeSampleBadInput):
    """ Using invalid values for any attribute must raise exceptions """

