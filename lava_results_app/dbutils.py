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

import hashlib
import os
import yaml
import sys
import logging
import decimal
from urllib.parse import quote

from collections import OrderedDict  # pylint: disable=unused-import

from lava_common.utils import debian_package_version
from lava_results_app.models import (
    TestSuite,
    TestSet,
    TestCase,
    TestData,
    ActionData,
    MetaType,
)
from django.core.exceptions import MultipleObjectsReturned
from lava_common.timeout import Timeout


def _check_for_testset(result_dict, suite):
    """
    The presence of the test_set key indicates the start and usage of a TestSet.
    Get or create and populate the definition based on that set.
    # {date: pass, test_definition: install-ssh, test_set: first_set}
    :param result_dict: lava-test-shell results
    :param suite: current test suite
    """
    logger = logging.getLogger('lava-master')
    testset = None
    if 'set' in result_dict:
        set_name = result_dict['set']
        if set_name != quote(set_name):
            msg = "Invalid testset name '%s', ignoring." % set_name
            suite.job.set_failure_comment(msg)
            logger.warning(msg)
            return None
        testset, _ = TestSet.objects.get_or_create(name=set_name, suite=suite)
        logger.debug("%s", testset)
    return testset


def append_failure_comment(job, msg):
    if not job.failure_comment:
        job.failure_comment = ''
    job.failure_comment += msg[:256]
    job.save(update_fields=["failure_comment"])


def create_metadata_store(results, job):
    """
    Uses the OrderedDict import to correctly handle
    the yaml.load
    """
    if 'extra' not in results:
        return None
    level = results.get('level')
    if level is None:
        return None

    logger = logging.getLogger('lava-master')
    stub = "%s-%s-%s.yaml" % (results['definition'], results['case'], level)
    meta_filename = os.path.join(job.output_dir, 'metadata', stub)
    os.makedirs(os.path.dirname(meta_filename), mode=0o755, exist_ok=True)
    if os.path.exists(meta_filename):
        with open(meta_filename, 'r') as existing_store:
            data = yaml.load(existing_store)
        data.update(results['extra'])
    else:
        data = results['extra']
    try:
        with open(meta_filename, 'w') as extra_store:
            yaml.dump(data, extra_store)
    except (OSError, IOError) as exc:  # LAVA-847
        msg = "[%d] Unable to create metadata store: %s" % (job.id, exc)
        logger.error(msg)
        append_failure_comment(job, msg)
        return None
    return meta_filename


def map_scanned_results(results, job, meta_filename):  # pylint: disable=too-many-branches,too-many-statements,too-many-return-statements
    """
    Sanity checker on the logged results dictionary
    :param results: results logged via the slave
    :param job: the current test job
    :param meta_filename: YAML store for results metadata
    :return: the TestCase object that should be saved to the database.
             None on error.
    """
    logger = logging.getLogger('lava-master')

    if not isinstance(results, dict):
        append_failure_comment(job, "[%d] %s is not a dictionary" % (job.id, results))
        return None

    if not {"definition", "case", "result"}.issubset(set(results.keys())):
        append_failure_comment(job, "Missing some keys (\"definition\", \"case\" or \"result\") in %s" % results)
        return None

    if 'extra' in results:
        results['extra'] = meta_filename

    metadata = yaml.dump(results)
    if len(metadata) > 4096:  # bug 2471 - test_length unit test
        msg = "[%d] Result metadata is too long. %s" % (job.id, metadata)
        logger.error(msg)
        append_failure_comment(job, msg)
        metadata = ""

    suite, _ = TestSuite.objects.get_or_create(name=results["definition"], job=job)
    testset = _check_for_testset(results, suite)

    name = results["case"].strip()

    test_case = None
    if suite.name == "lava":
        try:
            result_val = TestCase.RESULT_MAP[results['result']]
        except KeyError:
            logger.error("[%d] Unable to MAP result \"%s\"", job.id, results['result'])
            return None

        measurement = None
        units = ''
        if 'duration' in results:
            measurement = results['duration']
            units = 'seconds'
        test_case = TestCase(name=name,
                             suite=suite,
                             test_set=testset,
                             metadata=metadata,
                             measurement=measurement,
                             units=units,
                             result=result_val)

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
            return None
        try:
            test_case = TestCase(name=name,
                                 suite=suite,
                                 test_set=testset,
                                 result=TestCase.RESULT_MAP[result],
                                 metadata=metadata,
                                 measurement=measurement,
                                 units=units)
        except decimal.InvalidOperation:
            logger.exception("[%d] Unable to create test case %s", job.id, name)
    return test_case


def _add_parameter_metadata(prefix, definition, dictionary, label):
    if 'parameters' in definition and isinstance(definition['parameters'], dict):
        for paramkey, paramvalue in definition['parameters'].items():
            if paramkey == 'yaml_line':
                continue
            dictionary['%s.%s.parameters.%s' % (prefix, label, paramkey)] = paramvalue


def _get_job_metadata(job):
    retval = {}
    # Add original_definition checksum to metadata
    retval.update({
        'definition-checksum': hashlib.md5(
            job.original_definition.encode('utf-8')).hexdigest()
    })
    # Add lava-server-version to metadata
    packaged = debian_package_version(pkg="lava-server", split=False)
    if packaged:
        retval.update({
            'lava-server-version': packaged
        })
    return retval


def _get_action_metadata(data):  # pylint: disable=too-many-branches,too-many-nested-blocks,too-many-statements
    if not isinstance(data, list):
        return None
    retval = {}
    for action in data:
        deploy = [dict.get(action, 'deploy')]
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
        boot = [dict.get(action, 'boot')]
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
        test = [dict.get(action, 'test')]
        count = 0
        for block in test:
            if not block:
                continue
            namespace = block.get('namespace', None)
            definitions = [dict.get(block, 'definitions')][0]
            if not definitions:
                monitors = [dict.get(block, 'monitors')][0]
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
                        steps = [dict.get(run, 'steps')][0] if run else None
                        if steps is not None and 'lava-test-case' in steps:
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


def build_action(action_data, testdata, submission):
    # test for a known section
    logger = logging.getLogger('lava-master')
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
    action_meta, _ = MetaType.objects.get_or_create(name=type_name,
                                                    metatype=metatype)
    max_retry = action_data.get('max_retries')

    # find corresponding test case
    match_case = None
    test_cases = TestCase.objects.filter(suite__job=testdata.testjob, suite__name='lava')
    for case in test_cases:
        if 'level' in case.action_metadata:
            if case.action_metadata['level'] == action_data['level']:
                match_case = case

    # maps the static testdata derived from the definition to the runtime pipeline construction
    ActionData.objects.create(
        action_name=action_data['name'],
        action_level=action_data['level'],
        action_summary=action_data['summary'],
        testdata=testdata,
        action_description=action_data['description'],
        meta_type=action_meta,
        max_retries=max_retry,
        timeout=int(Timeout.parse(action_data['timeout'])),
        testcase=match_case
    )


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
    logger = logging.getLogger('lava-master')
    try:
        submission_data = yaml.safe_load(job.definition)
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

    # get job-action metadata
    if description is None:
        logger.warning("[%s] skipping empty description", job.id)
        return False
    if not description_data:
        logger.warning("[%s] skipping invalid description data", job.id)
        return False
    if 'job' not in description_data:
        logger.warning("[%s] skipping description without a job.", job.id)
        return False
    action_values = _get_action_metadata(description_data['job']['actions'])
    for key, value in action_values.items():
        if not key or not value:
            logger.warning('[%s] Missing element in job. %s: %s', job.id, key, value)
            continue
        testdata.attributes.create(name=key, value=value)

    # get common job metadata
    job_metadata = _get_job_metadata(job)
    for key, value in job_metadata.items():
        testdata.attributes.create(name=key, value=value)

    # get metadata from device
    device_values = {}
    device_values['target.device_type'] = job.requested_device_type
    for key, value in device_values.items():
        if not key or not value:
            logger.warning('[%s] Missing element in device. %s: %s', job.id, key, value)
            continue
        testdata.attributes.create(name=key, value=value)

    # Add metadata from job submission data.
    if "metadata" in submission_data:
        for key in submission_data["metadata"]:
            value = submission_data["metadata"][key]
            if not key or not value:
                logger.warning('[%s] Missing element in job. %s: %s', job.id, key, value)
                continue
            testdata.attributes.create(name=key, value=value)

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
        'logged', 'level', 'metadata', 'url', 'name', 'id'
    ]


def export_testcase(testcase, with_buglinks=False):
    """
    Returns string versions of selected elements of a TestCase
    Unicode causes issues with CSV and can complicate YAML parsing
    with non-python parsers.
    :param testcase: list of TestCase objects
    :return: Dictionary containing relevant information formatted for export
    """
    metadata = dict(testcase.action_metadata) if testcase.action_metadata else {}
    extra_source = []
    extra_data = metadata.get('extra', None)
    if isinstance(extra_data, str) and os.path.exists(extra_data):
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
        'level': metadata.get('level', ''),
        'url': str(testcase.get_absolute_url()),
        'id': str(testcase.id),
        'logged': str(testcase.logged),
        'metadata': metadata,
    }
    if with_buglinks:
        casedict['buglinks'] = [str(url) for url in testcase.buglinks.values_list('url', flat=True)]

    return casedict


def testsuite_export_fields():
    """
    Keep this list in sync with the keys in export_testsuite
    :return: list of fields used in export_testsuite
    """
    return [
        'name', 'job', 'id'
    ]


def export_testsuite(testsuite):
    """
    Returns string versions of selected elements of a TestSuite
    :param testsuite: TestSuite object
    :return: Dictionary containing relevant information formatted for export
    """
    suitedict = {
        'name': str(testsuite.name),
        'job': str(testsuite.job_id),
        'id': str(testsuite.id),
    }
    return suitedict
