#!/usr/bin/env python
"""
Test cases for launch_control.sample module
"""

import launch_control.sample
from launch_control.sample import QualitativeSample


import random
from unittest import TestCase

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


class FixtureSample(object):
    """
    Fixture with a sample instance and helper factory methods
    """

    def setUp(self):
        self.sample = QualitativeSample(
                QualitativeSample.TEST_RESULT_PASS,
                'org.example.test')

    def _random_sample(self, **kwargs):
        """
        Make random pass/fail sample with other attributes specified by
        the caller.
        """
        return QualitativeSample(random.choice(['fail', 'pass']), **kwargs)


class QualitativeSampleConstruction(FixtureSample, TestCase):
    """ Check construction behavior for QualitativeSample """

    def test_constructor_requires_test_result(self):
        """ At least one argument is required: test_result """
        self.assertRaises(TypeError, QualitativeSample)

    def test_constructor_sets_test_result(self):
        """ Argument test_result is stored correctly for both supported
        values. """
        sample1 = QualitativeSample('fail')
        self.assertEqual(sample1.test_result, 'fail')
        sample2 = QualitativeSample('pass')
        self.assertEqual(sample2.test_result, 'pass')

    def test_constructor_defaults_test_id_to_None(self):
        """ Argument test_id defaults to None """
        sample = self._random_sample()
        self.assertEqual(sample.test_id, None)

    def test_constructor_sets_test_id(self):
        """ Argument test_id is stored correctly """
        sample = self._random_sample(test_id='test_id')
        self.assertEqual(sample.test_id, 'test_id')

    def test_constructor_defaults_message_to_None(self):
        """ Argument message defaults to None """
        sample = self._random_sample()
        self.assertEqual(sample.message, None)
    def test_constructor_sets_bytestring_message(self):
        """ Argument message is stored correctly (for byte strings) """
        sample = self._random_sample(message='foobar')
        self.assertEqual(sample.message, 'foobar')
    def test_constructor_sets_unicode_message(self):
        """ Argument message is stored correctly (for unicode strings)
        """
        sample = self._random_sample(message=u'foobar')
        self.assertEqual(sample.message, u'foobar')
    def test_constructor_defaults_timestamp_to_None(self):
        """ Argument timestamp defaults to None """
        sample = self._random_sample()
        self.assertEqual(sample.timestamp, None)
    def test_constructor_sets_timestamp(self):
        """ Argument timestamp is stored correctly """
        sample = self._random_sample(timestamp=1245)
        self.assertEqual(sample.timestamp, 1245)
    def test_constructor_defaults_duration_to_None(self):
        """ Argument duration defaults to None """
        sample = self._random_sample()
        self.assertEqual(sample.duration, None)
    def test_constructor_sets_duration(self):
        """ Argument duration is stored correctly """
        sample = self._random_sample(duration=10)
        self.assertEqual(sample.duration, 10)

class QualitativeSampleGoodInput(FixtureSample, TestCase):
    """ Using valid values for all attributes must work correctly """

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

    def test_timestamp_can_be_a_fixnum(self):
        self.sample.timestamp = 12345
        self.assertEqual(self.sample.timestamp, 12345)

    def test_timestamp_can_be_a_float(self):
        self.sample.timestamp = 12345.51
        self.assertAlmostEqual(self.sample.timestamp, 12345.51)

    def test_duration_can_be_None(self):
        self.sample.duration = None
        self.assertEqual(self.sample.duration, None)

    def test_duration_can_be_a_fixnum(self):
        self.sample.duration = 12345
        self.assertEqual(self.sample.duration, 12345)

    def test_duration_can_be_a_float(self):
        self.sample.duration = 12345.51
        self.assertAlmostEqual(self.sample.duration, 12345.51)


class QualitativeSampleBadInput(FixtureSample, TestCase):
    """ Using invalid values for any attribute must raise exceptions """

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

    def test_timestamp_cannot_be_negative(self):
        self.assertRaises(ValueError, setattr, self.sample, 'timestamp', -1)

    def test_timestamp_cannot_be_non_number(self):
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', False)
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', 'booo')
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', '')
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', {})
        self.assertRaises(TypeError, setattr, self.sample, 'timestamp', [])

    def test_duration_cannot_be_negative(self):
        self.assertRaises(ValueError, setattr, self.sample, 'duration', -1)

    def test_duration_cannot_be_non_number(self):
        self.assertRaises(TypeError, setattr, self.sample, 'duration', False)
        self.assertRaises(TypeError, setattr, self.sample, 'duration', 'booo')
        self.assertRaises(TypeError, setattr, self.sample, 'duration', '')
        self.assertRaises(TypeError, setattr, self.sample, 'duration', {})
        self.assertRaises(TypeError, setattr, self.sample, 'duration', [])

