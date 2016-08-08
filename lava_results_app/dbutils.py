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
import urllib
import logging
from django.db import transaction
from lava_results_app.models import (
    TestSuite,
    TestSet,
    TestCase,
    TestData,
    ActionData,
    MetaType,
)
from django.core.exceptions import MultipleObjectsReturned
from lava_dispatcher.pipeline.action import Timeout
# pylint: disable=no-member


def _check_for_testset(result_dict, suite):
    """
    The presence of the test_set key indicates the start and usage of a TestSet.
    Get or create and populate the definition based on that set.
    # {date: pass, test_definition: install-ssh, test_set: first_set}
    :param result_dict: lava-test-shell results
    :param suite: current test suite
    """
    logger = logging.getLogger('dispatcher-master')
    testset = None
    if 'set' in result_dict:
        set_name = result_dict['set']
        if set_name != urllib.quote(set_name):
            msg = "Invalid testset name '%s', ignoring." % set_name
            suite.job.set_failure_comment(msg)
            logger.warning(msg)
            return None
        testset, created = TestSet.objects.get_or_create(name=set_name, suite=suite)
        if created:
            testset.save()
        logger.debug("%s", testset)
    return testset


def map_scanned_results(results, job):  # pylint: disable=too-many-branches,too-many-statements
    """
    Sanity checker on the logged results dictionary
    :param results: results logged via the slave
    :param job: the current test job
    :return: False on error, else True
    """
    logger = logging.getLogger('dispatcher-master')

    if not isinstance(results, dict):
        logger.debug("%s is not a dictionary", results)
        return False

    if not set(["definition", "case", "result"]).issubset(set(results.keys())):
        logger.error("Missing some keys (\"definition\", \"case\" or \"result\") in %s", results)
        return False

    suite, created = TestSuite.objects.get_or_create(name=results["definition"], job=job)
    if created:
        suite.save()
    testset = _check_for_testset(results, suite)

    name = results["case"]
    if suite.name == "lava":
        match_action = None
        if "level" in results:
            match_action = ActionData.objects.filter(
                action_level=str(results['level']),
                testdata__testjob=suite.job)
            if match_action:
                match_action = match_action[0]
                if 'duration' in results:
                    match_action.duration = results['duration']
                if 'timeout' in results:
                    match_action.timeout = results['timeout']  # duration, positive integer
        try:
            result_val = TestCase.RESULT_MAP[results['result']]
        except KeyError:
            logger.error("Unable to MAP result \"%s\"", results['result'])
            return False

        try:
            # For lava test suite, the test (actions) can be seen two times.
            case = TestCase.objects.get(name=name, suite=suite)
            case.test_set = testset
            case.metadata = yaml.dump(results)
            case.result = result_val
        except TestCase.DoesNotExist:
            case = TestCase.objects.create(name=name,
                                           suite=suite,
                                           test_set=testset,
                                           metadata=yaml.dump(results),
                                           result=result_val)
        with transaction.atomic():
            case.save()
            if match_action:
                match_action.testcase = case
                match_action.save(update_fields=['testcase', 'duration', 'timeout'])

    else:
        result = results["result"]
        measurement = None
        units = ''
        if testset:
            logger.debug("%s/%s/%s %s", suite, testset, name, result)
        else:
            logger.debug("%s/%s %s", suite, name, result)
        if 'measurement' in results:
            measurement = results['measurement']
        if 'units' in results:
            units = results['units']
            logger.debug("%s/%s %s%s", suite, name, measurement, units)
        if result not in TestCase.RESULT_MAP:
            logger.warning("[%d] Unrecognised result: '%s' for test case '%s'", job.id, result, name)
            return False
        TestCase.objects.create(
            name=name,
            suite=suite,
            test_set=testset,
            result=TestCase.RESULT_MAP[result],
            measurement=measurement,
            units=units
        ).save()
    return True


def _get_job_metadata(data):  # pylint: disable=too-many-branches
    if not isinstance(data, list):
        return None
    retval = {}
    for action in data:
        deploy = [reduce(dict.get, ['deploy'], action)]
        count = 0
        for block in deploy:
            if not block:
                continue
            namespace = block.get('namespace', None)
            prefix = "deploy.%d.%s" % (count, namespace) if namespace else 'deploy.%d' % count
            value = block.get('method', None)
            if value:
                retval['%s.method' % prefix] = value
                count += 1
        boot = [reduce(dict.get, ['boot'], action)]
        count = 0
        for block in boot:
            if not block:
                continue
            namespace = block.get('namespace', None)
            prefix = "boot.%d.%s" % (count, namespace) if namespace else 'boot.%d' % count
            value = block.get('commands', None)
            if value:
                retval['%s.commands' % prefix] = value
            value = block.get('method', None)
            if value:
                retval['%s.method' % prefix] = value
            value = block.get('type', None)
            if value:
                retval['%s.type' % prefix] = value
            count += 1
        test = [reduce(dict.get, ['test'], action)]
        count = 0
        for block in test:
            if not block:
                continue
            namespace = block.get('namespace', None)
            definitions = [reduce(dict.get, ['definitions'], block)][0]
            for definition in definitions:
                if definition['from'] == 'inline':
                    # an inline repo without test cases will not get reported.
                    if 'lava-test-case' in [reduce(dict.get, ['repository', 'run', 'steps'], definition)][0]:
                        prefix = "test.%d.%s" % (count, namespace) if namespace else 'test.%d' % count
                    else:
                        # store the fact that an inline exists but would not generate any testcases
                        prefix = 'omitted.%d.%s' % (count, namespace) if namespace else 'omitted.%d' % count
                    retval['%s.inline.name' % prefix] = definition['name']
                    retval['%s.inline.path' % prefix] = definition['path']
                else:
                    prefix = "test.%d.%s" % (count, namespace) if namespace else 'test.%d' % count
                    # FIXME: what happens with remote definition without lava-test-case?
                    retval['%s.definition.name' % prefix] = definition['name']
                    retval['%s.definition.path' % prefix] = definition['path']
                    retval['%s.definition.from' % prefix] = definition['from']
                    retval['%s.definition.repository' % prefix] = definition['repository']
                count += 1
    return retval


def _get_device_metadata(data):
    hostname = data.get('hostname', None)
    devicetype = data.get('device_type', None)
    return {
        'target.hostname': hostname,
        'target.device_type': devicetype
    }


def build_action(action_data, testdata, submission):
    # test for a known section
    logger = logging.getLogger('dispatcher-master')
    if 'section' not in action_data:
        logger.warning("Invalid action data - missing section")
        return

    metatype = MetaType.get_section(action_data['section'])
    if metatype is None:  # 0 is allowed
        logger.debug("Unrecognised metatype in action_data: %s", action_data['section'])
        return
    # lookup the type from the job definition.
    type_name = MetaType.get_type_name(action_data['section'], submission)
    if not type_name:
        logger.debug(
            "type_name failed for %s metatype %s",
            action_data['section'], MetaType.TYPE_CHOICES[metatype])
        return
    action_meta, created = MetaType.objects.get_or_create(
        name=type_name, metatype=metatype)
    if created:
        action_meta.save()
    max_retry = None
    if 'max_retries' in action_data:
        max_retry = action_data['max_retries']

    # maps the static testdata derived from the definition to the runtime pipeline construction
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
        logger.exception("[%s] %s", job.id, exc)
        return False
    try:
        testdata, created = TestData.objects.get_or_create(testjob=job)
    except MultipleObjectsReturned:
        # only happens for small number of jobs affected by original bug.
        logger.info("[%s] skipping alteration of duplicated TestData", job.id)
        return False
    if not created:
        # prevent updates of existing TestData
        logger.debug("[%s] skipping alteration of existing TestData", job.id)
        return False
    testdata.save()

    # get job-action metadata
    action_values = _get_job_metadata(description_data['job']['actions'])
    for key, value in action_values.items():
        if not key or not value:
            logger.warning('[%s] Missing element in job. %s: %s', job.id, key, value)
            continue
        testdata.attributes.create(name=key, value=value)

    # get metadata from device
    device_values = _get_device_metadata(description_data['device'])
    for key, value in device_values.items():
        if not key or not value:
            logger.warning('[%s] Missing element in device. %s: %s', job.id, key, value)
            continue
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
    :param testcase: list of TestCase objects
    :return: Dictionary containing relevant information formatted for export
    """
    actiondata = testcase.action_data
    duration = float(actiondata.duration) if actiondata else ''
    timeout = actiondata.timeout if actiondata else ''
    level = actiondata.action_level if actiondata else None
    casedict = {
        'name': str(testcase.name),
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
