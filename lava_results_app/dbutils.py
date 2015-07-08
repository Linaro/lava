# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.

import yaml
import logging
from django.db import transaction
from collections import OrderedDict
from lava_results_app.models import (
    TestSuite,
    TestSet,
    TestCase,
    TestData,
    ActionData,
    MetaType,
)
from lava_dispatcher.pipeline.action import Timeout
# pylint: disable=no-member


METADATA_MAPPING_DESCRIPTION = {
    "boot.commands": ["job", "actions", "boot", "commands"],
    "boot.method": ["job", "actions", "boot", "method"],
    "boot.type": ["job", "actions", "boot", "type"],
    "deploy.os": ["job", "actions", "deploy", "os"],
    "deploy.ramdisk-type": ["job", "actions", "deploy", "ramdisk-type"],
    "target.hostname": ["device", "hostname"],
    "target.device_type": ["device", "device_type"]
}


def _test_case(name, suite, result, testset=None, testshell=False):
    """
    Create a TestCase for the specified name and result
    :param name: name of the testcase to create
    :param suite: current TestSuite
    :param result: the result for this TestCase
    :param testset: Use a TestSet if supplied.
    :param testshell: handle lava-test-shell outside a TestSet.
    :return:
    """
    logger = logging.getLogger('dispatcher-master')
    if testshell:
        TestCase.objects.create(
            name=name,
            suite=suite,
            result=TestCase.RESULT_MAP[result]
        ).save()
    elif testset:
        TestCase.objects.create(
            name=name,
            suite=suite,
            test_set=testset,
            result=TestCase.RESULT_MAP[result]
        ).save()
    else:
        try:
            metadata = yaml.dump(result)
        except yaml.YAMLError:
            # FIXME: this may need to be reported to the user
            logger.warning("Unable to store metadata %s for %s as YAML", result, name)
            metadata = None
        match_action = None
        # the action level should exist already
        if 'level' in result and metadata:
            match_action = ActionData.objects.filter(
                action_level=str(result['level']),
                testdata__testjob=suite.job)
            if match_action:
                match_action = match_action[0]
                if 'duration' in result:
                    match_action.duration = result['duration']
                if 'timeout' in result:
                    match_action.timeout = result['timeout']  # duration, positive integer
        case = TestCase.objects.create(
            name=name,
            suite=suite,
            test_set=testset,
            metadata=metadata,
            result=TestCase.RESULT_UNKNOWN
        )
        with transaction.atomic():
            case.save()
            if match_action:
                match_action.testcase = case
                match_action.save(update_fields=['testcase', 'duration', 'timeout'])


def _check_for_testset(result_dict, suite):
    """
    Within a lava-test-shell, an OrderedDict indicates the start of a
    TestSet. Handle all results in the OrderedDict as part of that set.
    Handle all other results within the lava-test-shell items without using a TestSet.
    :param result_dict: lava-test-shell results
    :param suite: current test suite
    """
    for shell_testcase, shell_result in result_dict.items():
        if type(shell_result) == OrderedDict:
            # catch the testset
            testset = TestSet.objects.create(
                name=shell_testcase,
                suite=suite
            )
            testset.save()
            for set_casename, set_result in shell_result.items():
                _test_case(set_casename, suite, set_result, testset=testset)
        elif shell_testcase == 'level':
            # needs to be stored in the existing testcase, not a new one
            pass
        else:
            _test_case(shell_testcase, suite, shell_result, testshell=True)


def map_scanned_results(scanned_dict, job):
    """
    Sanity checker on the logged results dictionary
    :param scanned_dict: results logged via the slave
    :param suite: the current test suite
    :return: False on error, else True
    """
    logger = logging.getLogger('dispatcher-master')
    if type(scanned_dict) is not dict:
        logger.debug("%s is not a dictionary", scanned_dict)
        return False
    if 'results' not in scanned_dict:
        logger.debug("missing results in %s", scanned_dict.keys())
        return False
    results = scanned_dict['results']
    if 'testsuite' in results:
        suite = TestSuite.objects.get_or_create(name=results['testsuite'], job=job)[0]
        logger.debug("%s" % suite)
    else:
        suite = TestSuite.objects.get_or_create(name='lava', job=job)[0]
    for name, result in results.items():
        if name == 'testsuite':
            # already handled
            pass
        elif name == 'testset':
            _check_for_testset(result, suite)
        else:
            _test_case(name, suite, result, testshell=(suite.name != 'lava'))
    return True


def _get_nested_value(data, mapping):
    # get the value from a nested dictionary based on keys given in 'mapping'.
    value = data
    for key in mapping:
        try:
            value = value[key]
        except TypeError:
            # check case when nested value is list and not dict.
            for item in value:
                if key in item:
                    value = item[key]
        except KeyError:
            return None

    return value


def build_action(action_data, testdata, submission):
    # test for a known section
    logger = logging.getLogger('lava_results_app')
    if 'section' not in action_data:
        logger.warn("Invalid action data - missing section")
        return

    metatype = MetaType.get_section(action_data['section'])
    if metatype is None:  # 0 is allowed
        logger.debug("Unrecognised metatype in action_data: %s" % action_data['section'])
        return
    # lookup the type from the job definition.
    type_name = MetaType.get_type_name(action_data['section'], submission)
    if not type_name:
        logger.debug(
            "type_name failed for %s metatype %s" % (
                action_data['section'], MetaType.TYPE_CHOICES[metatype]))
        return
    action_meta, created = MetaType.objects.get_or_create(
        name=type_name, metatype=metatype)
    if created:
        action_meta.save()
    max_retry = None
    if 'max_retries' in action_data:
        max_retry = action_data['max_retries']

    action = ActionData.objects.create(
        action_name=action_data['name'],
        action_level=action_data['level'],
        action_summary=action_data['summary'],
        testdata=testdata,
        action_description=action_data['description'],
        meta_type=action_meta,
        max_retries=max_retry,
        timeout=int(Timeout.parse(action_data['timeout']))
    )
    with transaction.atomic():
        action.save()


def walk_actions(data, testdata, submission):
    for action in data:
        build_action(action, testdata, submission)
        if 'pipeline' in action:
            walk_actions(action['pipeline'], testdata, submission)


def map_metadata(description, job):
    """
    Generate metadata from the combination of the pipeline definition
    file (after any parsing for protocols) and the pipeline description
    into static metadata (TestData) related to this specific job
    The description itself remains outside the database - it will need
    to be made available as a download link.
    :param description: the pipeline description output
    :param job: the TestJob to associate
    :return: True on success, False on error
    """
    logger = logging.getLogger('dispatcher-master')
    try:
        submission_data = yaml.load(job.definition)
        description_data = yaml.load(description)
    except yaml.YAMLError as exc:
        logger.exception("[%s] %s" % (job.id, exc))
        return False
    testdata = TestData.objects.create(testjob=job)
    testdata.save()
    # Add metadata from description data.
    for key in METADATA_MAPPING_DESCRIPTION:
        value = _get_nested_value(
            description_data,
            METADATA_MAPPING_DESCRIPTION[key]
        )
        if value:
            testdata.attributes.create(name=key, value=value)

    # Add metadata from job submission data.
    if "metadata" in submission_data:
        for key in submission_data["metadata"]:
            testdata.attributes.create(name=key,
                                       value=submission_data["metadata"][key])

    walk_actions(description_data['pipeline'], testdata, submission_data)
    return True


def testcase_export_fields():
    """
    Keep this list in sync with the keys in export_testcase
    :return: list of fields used in export_testcase
    """
    return [
        'job', 'suite', 'result', 'measurement', 'unit',
        'duration', 'timeout',
        'logged', 'level', 'metadata', 'url',
    ]


def export_testcase(testcase):
    """
    Returns string versions of selected elements of a TestCase
    Unicode causes issues with CSV and can complicate YAML parsing
    with non-python parsers.
    :param testcases: list of TestCase objects
    :return: Dictionary containing relevant information formatted for export
    """
    actiondata = testcase.action_data
    duration = float(actiondata.duration) if actiondata else ''
    timeout = actiondata.timeout if actiondata else ''
    level = actiondata.action_level if actiondata else None
    casedict = {
        'job': str(testcase.suite.job_id),
        'suite': str(testcase.suite.name),
        'result': str(testcase.result_code),
        'measurement': str(testcase.measurement),
        'unit': str(testcase.units),
        'duration': str(duration),
        'timeout': str(timeout),
        'logged': str(testcase.logged),
        'level': str(level),
        'metadata': dict(testcase.action_metadata) if testcase.action_metadata else {},
        'url': str(testcase.get_absolute_url()),
    }
    return casedict
