#!/usr/bin/env python
"""
Test cases for launch_control.sample module
"""

from launch_control.sample import QualitativeSample
from launch_control.testing.call_helper import ObjectFactory
import launch_control.sample


from unittest import TestCase
import datetime

# Hack, see DocTestAwareTestLoader for insight
__doctest_module__ = launch_control.sample


class QualitativeSampleClassProperties(TestCase):
    """"Check for properties of QualitativeSample class"""
    def test_TEST_RESULT_PASS_is_pass(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_PASS, 'pass')

    def test_TEST_RESULT_FAIL_is_fail(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_FAIL, 'fail')

    def test_TEST_RESULT_SKIP_is_skip(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_SKIP, 'skip')

    def test_TEST_RESULT_CRASH_is_crash(self):
        self.assertEqual(QualitativeSample.TEST_RESULT_CRASH, 'crash')


class QualitativeSampleConstruction(TestCase):
    """ Check construction behavior for QualitativeSample """

    def setUp(self):
        super(QualitativeSampleConstruction, self).setUp()
        self.factory = ObjectFactory(QualitativeSample)

    def test_constructor_requires_test_result(self):
        """ At least one argument is required: test_result """
        self.assertRaises(TypeError, QualitativeSample)

    def test_constructor_sets_test_result(self):
        """ Argument test_result is stored correctly for both supported
        values. """
        sample = self.factory(test_result='fail')
        self.assertEqual(sample.test_result, 'fail')
        sample = self.factory(test_result='pass')
        self.assertEqual(sample.test_result, 'pass')
        sample = self.factory(test_result='skip')
        self.assertEqual(sample.test_result, 'skip')
        sample = self.factory(test_result='crash')
        self.assertEqual(sample.test_result, 'crash')

    def test_constructor_defaults_test_id_to_None(self):
        """ Argument test_id defaults to None """
        sample = self.factory(test_id=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.test_id, None)

    def test_constructor_sets_test_id(self):
        """ Argument test_id is stored correctly """
        sample = self.factory(test_id='test_id')
        self.assertEqual(sample.test_id, 'test_id')

    def test_constructor_defaults_message_to_None(self):
        """ Argument message defaults to None """
        sample = self.factory(message=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.message, None)

    def test_constructor_sets_bytestring_message(self):
        """ Argument message is stored correctly (for byte strings) """
        sample = self.factory(message='foobar')
        self.assertEqual(sample.message, 'foobar')

    def test_constructor_sets_unicode_message(self):
        """ Argument message is stored correctly (for unicode strings)
        """
        sample = self.factory(message=u'foobar')
        self.assertEqual(sample.message, u'foobar')

    def test_constructor_defaults_timestamp_to_None(self):
        """ Argument timestamp defaults to None """
        sample = self.factory(timestamp=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.timestamp, None)

    def test_constructor_sets_timestamp(self):
        """ Argument timestamp is stored correctly """
        timestamp = self.factory.dummy.timestamp
        sample = self.factory(timestamp=timestamp)
        self.assertEqual(sample.timestamp, timestamp)

    def test_constructor_defaults_duration_to_None(self):
        """ Argument duration defaults to None """
        sample = self.factory(duration=ObjectFactory.DEFAULT_VALUE)
        self.assertEqual(sample.duration, None)

    def test_constructor_sets_duration(self):
        """ Argument duration is stored correctly """
        duration = self.factory.dummy.duration
        sample = self.factory(duration=duration)
        self.assertEqual(sample.duration, duration)


class QualitativeSampleGoodInput(TestCase):
    """ Using valid values for all attributes must work correctly """

    def setUp(self):
        super(QualitativeSampleGoodInput, self).setUp()
        factory = ObjectFactory(QualitativeSample)
        self.sample = factory()

    def test_test_result_can_be_set_to_pass(self):
        self.sample.test_result = 'pass'
        self.assertEqual(self.sample.test_result, 'pass')

    def test_test_result_can_be_set_to_fail(self):
        self.sample.test_result = 'fail'
        self.assertEqual(self.sample.test_result, 'fail')

    def test_test_result_can_be_set_to_skip(self):
        self.sample.test_result = 'skip'
        self.assertEqual(self.sample.test_result, 'skip')

    def test_test_result_can_be_set_to_crash(self):
        self.sample.test_result = 'crash'
        self.assertEqual(self.sample.test_result, 'crash')

    def test_test_id_can_be_a_single_word(self):
        self.sample.test_id = 'word'
        self.assertEqual(self.sample.test_id, 'word')

    def test_test_id_can_be_a_dotted_sentence(self):
        self.sample.test_id = 'dotted.sentence.that.is.not.a.domain.name'
        self.assertEqual(self.sample.test_id, 'dotted.sentence.that.is.not.a.domain.name')

    def test_test_id_can_contain_hypens(self):
        self.sample.test_id = 'hypen-okay'
        self.assertEqual(self.sample.test_id, 'hypen-okay')

    def test_test_id_can_contain_underscores(self):
        self.sample.test_id = 'underscore_okay'
        self.assertEqual(self.sample.test_id, 'underscore_okay')

    def test_test_id_can_be_uppercase(self):
        self.sample.test_id = 'UPPERCASE'
        self.assertEqual(self.sample.test_id, 'UPPERCASE')

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
        timestamp = datetime.datetime(2010, 1, 1, 15, 00)
        self.sample.timestamp = timestamp
        self.assertEqual(self.sample.timestamp, timestamp)

    def test_duration_can_be_None(self):
        self.sample.duration = None
        self.assertEqual(self.sample.duration, None)

    def test_duration_can_be_timedelta(self):
        duration = datetime.timedelta(minutes=2, seconds=5)
        self.sample.duration = duration
        self.assertEqual(self.sample.duration, duration)


class QualitativeSampleBadInput(TestCase):
    """ Using invalid values for any attribute must raise exceptions """

    def setUp(self):
        super(QualitativeSampleBadInput, self).setUp()
        factory = ObjectFactory(QualitativeSample)
        self.sample = factory()

    def test_test_result_cannot_be_None(self):
        self.assertRaises(TypeError, setattr, self.sample, 'test_result', None)

    def test_test_result_cannot_be_empty(self):
        self.assertRaises(ValueError, setattr, self.sample, 'test_result', '')

    def test_test_result_cannot_be_arbitrary(self):
        self.assertRaises(ValueError, setattr, self.sample, 'test_result', 'bonk')
        self.assertRaises(ValueError, setattr, self.sample, 'test_result', 'puff')

    def test_test_id_cannot_have_spaces(self):
        self.assertRaises(ValueError, setattr, self.sample, 'test_id',
                'something that does not look like a domain name')

    def test_test_id_cannot_be_empty(self):
        self.assertRaises(ValueError, setattr, self.sample, 'test_id', '')

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

    def test_duration_cannot_be_negative(self):
        duration = datetime.timedelta(microseconds=-1)
        self.assertRaises(ValueError, setattr, self.sample, 'duration', duration)

    def test_duration_cannot_be_non_datetime(self):
        self.assertRaises(TypeError, setattr, self.sample, 'duration', 0)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', 152.5)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', -152.5)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', False)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', 'booo')
        self.assertRaises(TypeError, setattr, self.sample, 'duration', '')
        self.assertRaises(TypeError, setattr, self.sample, 'duration', {})
        self.assertRaises(TypeError, setattr, self.sample, 'duration', [])

