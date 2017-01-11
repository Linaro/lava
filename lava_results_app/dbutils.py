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

# pylint: disable=no-member,too-many-locals,too-many-nested-blocks,
# pylint: disable=too-many-return-statements,ungrouped-imports
import os
import yaml
import urllib
import logging
import django
import decimal
from django.db import transaction
from collections import OrderedDict  # pylint: disable=unused-import
from lava_results_app.models import (
    TestSuite,
    TestSet,
    TestCase,
    TestData,
    ActionData,
    MetaType,
)
from lava_results_app.utils import debian_package_version
from django.core.exceptions import MultipleObjectsReturned
from lava_dispatcher.pipeline.action import Timeout

if django.VERSION > (1, 10):
    from django.urls.exceptions import NoReverseMatch
    from django.urls import reverse
else:
    from django.core.urlresolvers import reverse
    from django.core.urlresolvers import NoReverseMatch


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


def append_failure_comment(job, msg):
    logger = logging.getLogger('dispatcher-master')
    if not job.failure_comment:
        job.failure_comment = ''
    job.failure_comment += msg[:256]
    logger.error(msg)


def create_metadata_store(results, job, level):
    """
    Uses the OrderedDict import to correctly handle
    the yaml.load
    """
    if 'extra' not in results:
        return None
    stub = "%s-%s-%s.yaml" % (results['definition'], results['case'], level)
    meta_filename = os.path.join(job.output_dir, 'metadata', stub)
    if not os.path.exists(os.path.dirname(meta_filename)):
        os.mkdir(os.path.dirname(meta_filename))
    if os.path.exists(meta_filename):
        with open(meta_filename, 'r') as existing_store:
            data = yaml.load(existing_store)
        data.update(results['extra'])
    else:
        data = results['extra']
    with open(meta_filename, 'w') as extra_store:
        yaml.dump(data, extra_store)
    return meta_filename


def map_scanned_results(results, job, meta_filename):  # pylint: disable=too-many-branches,too-many-statements,too-many-return-statements
    """
    Sanity checker on the logged results dictionary
    :param results: results logged via the slave
    :param job: the current test job
    :param meta_filename: YAML store for results metadata
    :return: False on error, else True
    """
    logger = logging.getLogger('dispatcher-master')

    if not isinstance(results, dict):
        append_failure_comment(job, "[%d] %s is not a dictionary" % (job.id, results))
        return False

    if not {"definition", "case", "result"}.issubset(set(results.keys())):
        append_failure_comment(job, "Missing some keys (\"definition\", \"case\" or \"result\") in %s" % results)
        return False

    if 'extra' in results:
        results['extra'] = meta_filename

    metadata_check = yaml.dump(results)
    if len(metadata_check) > 4096:  # bug 2471 - test_length unit test
        msg = "[%d] Result metadata is too long. %s" % (job.id, metadata_check)
        logger.error(msg)
        append_failure_comment(job, msg)
        return False

    suite, created = TestSuite.objects.get_or_create(name=results["definition"], job=job)
    if created:
        suite.save()
    testset = _check_for_testset(results, suite)

    name = results["case"]
    try:
        reverse('lava.results.testcase', args=[job.id, suite.name, name])
    except NoReverseMatch:
        append_failure_comment(
            job,
            "[%d] Unable to parse test case name as URL %s in suite %s" % (job.id, name, suite.name))
        return False
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
            logger.error("[%d] Unable to MAP result \"%s\"", job.id, results['result'])
            return False

        measurement = None
        units = ''
        if 'duration' in results:
            measurement = results['duration']
            units = 'seconds'
        try:
            # For lava test suite, the test (actions) can be seen two times.
            case = TestCase.objects.get(name=name, suite=suite)
            case.test_set = testset
            case.metadata = yaml.dump(results)
            case.result = result_val
            case.measurement = measurement
            case.units = units
        except TestCase.DoesNotExist:
            case = TestCase.objects.create(name=name,
                                           suite=suite,
                                           test_set=testset,
                                           metadata=yaml.dump(results),
                                           measurement=measurement,
                                           units=units,
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
        try:
            TestCase.objects.create(
                name=name,
                suite=suite,
                test_set=testset,
                result=TestCase.RESULT_MAP[result],
                metadata=yaml.dump(results),
                measurement=measurement,
                units=units
            ).save()
        except decimal.InvalidOperation:
            logger.exception("[%d] Unable to create test case %s", job.id, name)
    return True


def _add_parameter_metadata(prefix, definition, dictionary, label):
    if 'parameters' in definition and isinstance(definition['parameters'], dict):
        for paramkey, paramvalue in definition['parameters'].items():
            if paramkey == 'yaml_line':
                continue
            dictionary['%s.%s.parameters.%s' % (prefix, label, paramkey)] = paramvalue


def _get_job_metadata(data):  # pylint: disable=too-many-branches,too-many-nested-blocks,too-many-statements
    if not isinstance(data, list):
        return None
    retval = {}
    packaged = debian_package_version()
    if packaged:
        retval.update({
            'lava-server-version': packaged
        })
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
            if not definitions:
                monitors = [reduce(dict.get, ['monitors'], block)][0]
                if monitors:
                    if isinstance(monitors, list):
                        for monitor in monitors:
                            prefix = "test.%d.%s" % (count, namespace) if namespace else 'test.%d' % count
                            retval['%s.monitor.name' % prefix] = monitor['name']
                            count += 1
            else:
                for definition in definitions:
                    if definition['from'] == 'inline':
                        run = definition['repository'].get('run', None)
                        # an inline repo without test cases will not get reported.
                        if run and 'lava-test-case' in [reduce(dict.get, ['repository', 'run', 'steps'], definition)][0]:
                            prefix = "test.%d.%s" % (count, namespace) if namespace else 'test.%d' % count
                        else:
                            # store the fact that an inline exists but would not generate any testcases
                            prefix = 'omitted.%d.%s' % (count, namespace) if namespace else 'omitted.%d' % count
                        retval['%s.inline.name' % prefix] = definition['name']
                        _add_parameter_metadata(prefix=prefix, definition=definition,
                                                dictionary=retval, label='inline')
                        retval['%s.inline.path' % prefix] = definition['path']
                    else:
                        prefix = "test.%d.%s" % (count, namespace) if namespace else 'test.%d' % count
                        # FIXME: what happens with remote definition without lava-test-case?
                        retval['%s.definition.name' % prefix] = definition['name']
                        retval['%s.definition.path' % prefix] = definition['path']
                        retval['%s.definition.from' % prefix] = definition['from']
                        retval['%s.definition.repository' % prefix] = definition['repository']
                        _add_parameter_metadata(prefix=prefix, definition=definition,
                                                dictionary=retval, label='definition')
                    count += 1
    return retval


def _get_device_metadata(data):
    devicetype = data.get('device_type', None)
    return {
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
    type_name = MetaType.get_type_name(action_data, submission)
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
    if description is None:
        logger.warning("[%s] skipping empty description", job.id)
        return
    if not description_data:
        logger.warning("[%s] skipping invalid description data", job.id)
        return
    if 'job' not in description_data:
        logger.warning("[%s] skipping description without a job.", job.id)
        return
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
    metadata = dict(testcase.action_metadata) if testcase.action_metadata else {}
    extra_source = []
    extra_data = metadata.get('extra', None)
    if extra_data and isinstance(extra_data, unicode) and os.path.exists(extra_data):
        with open(metadata['extra'], 'r') as extra_file:
            items = yaml.load(extra_file, Loader=yaml.CLoader)
        # hide the !!python OrderedDict prefix from the output.
        for key, value in items.items():
            extra_source.append({key: value})
        metadata['extra'] = extra_source
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
        'metadata': metadata,
        'url': str(testcase.get_absolute_url()),
    }
    return casedict
