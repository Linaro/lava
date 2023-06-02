# Copyright (C) 2015-2018 Linaro Limited
#
# Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later


import decimal
import logging
import os
from urllib.parse import quote

from lava_common.version import __version__
from lava_common.yaml import yaml_safe_dump, yaml_safe_load
from lava_results_app.models import TestCase, TestSet, TestSuite


def _check_for_testset(result_dict, suite):
    """
    The presence of the test_set key indicates the start and usage of a TestSet.
    Get or create and populate the definition based on that set.
    # {date: pass, test_definition: install-ssh, test_set: first_set}
    :param result_dict: lava-test-shell results
    :param suite: current test suite
    """
    logger = logging.getLogger("lava-master")
    testset = None
    if "set" in result_dict:
        set_name = result_dict["set"]
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
        job.failure_comment = ""
    job.failure_comment += msg[:256]
    job.save(update_fields=["failure_comment"])


def create_metadata_store(results, job):
    """
    Uses the OrderedDict import to correctly handle
    the yaml.load
    """
    if "extra" not in results:
        return None
    level = results.get("level")
    if level is None:
        return None

    logger = logging.getLogger("lava-master")
    stub = "%s-%s-%s.yaml" % (results["definition"], results["case"], level)
    meta_filename = os.path.join(job.output_dir, "metadata", stub)
    os.makedirs(os.path.dirname(meta_filename), mode=0o755, exist_ok=True)
    if os.path.exists(meta_filename):
        with open(meta_filename) as existing_store:
            data = yaml_safe_load(existing_store)
        if data is None:
            data = {}
        data.update(results["extra"])
    else:
        data = results["extra"]
    try:
        with open(meta_filename, "w") as extra_store:
            yaml_safe_dump(data, extra_store)
    except OSError as exc:  # LAVA-847
        msg = "[%d] Unable to create metadata store: %s" % (job.id, exc)
        logger.error(msg)
        append_failure_comment(job, msg)
        return None
    return meta_filename


def map_scanned_results(results, job, starttc, endtc, meta_filename):
    """
    Sanity checker on the logged results dictionary
    :param results: results logged via the slave
    :param job: the current test job
    :param meta_filename: YAML store for results metadata
    :return: the TestCase object that should be saved to the database.
             None on error.
    """
    logger = logging.getLogger("lava-master")

    if not isinstance(results, dict):
        append_failure_comment(job, "[%d] %s is not a dictionary" % (job.id, results))
        return None

    if not {"definition", "case", "result"}.issubset(set(results.keys())):
        append_failure_comment(
            job, 'Missing some keys ("definition", "case" or "result") in %s' % results
        )
        return None

    if "extra" in results:
        results["extra"] = meta_filename

    metadata = yaml_safe_dump(results)
    if len(metadata) > 4096:  # bug 2471 - test_length unit test
        msg = "[%d] Result metadata is too long. %s" % (job.id, metadata)
        logger.warning(msg)
        append_failure_comment(job, msg)
        # Manually strip the results to keep some data
        stripped_results = {
            "case": results["case"],
            "definition": results["definition"],
            "result": results["result"],
        }
        if "error_type" in results:
            stripped_results["error_type"] = results["error_type"]
        metadata = yaml_safe_dump(stripped_results)
        if len(metadata) > 4096:
            metadata = ""

    suite, _ = TestSuite.objects.get_or_create(name=results["definition"], job=job)
    testset = _check_for_testset(results, suite)

    name = results["case"].strip()

    test_case = None
    if suite.name == "lava":
        try:
            result_val = TestCase.RESULT_MAP[results["result"]]
        except KeyError:
            logger.error('[%d] Unable to MAP result "%s"', job.id, results["result"])
            return None

        measurement = None
        units = ""
        if "duration" in results:
            measurement = results["duration"]
            units = "seconds"
        test_case = TestCase(
            name=name,
            suite=suite,
            test_set=testset,
            metadata=metadata,
            measurement=measurement,
            units=units,
            result=result_val,
        )

    else:
        result = results["result"]
        measurement = None
        units = ""
        if testset:
            logger.debug("%s/%s/%s %s", suite, testset, name, result)
        else:
            logger.debug("%s/%s %s", suite, name, result)
        if "measurement" in results:
            measurement = results["measurement"]
        if "units" in results:
            units = results["units"]
            logger.debug("%s/%s %s%s", suite, name, measurement, units)
        if result not in TestCase.RESULT_MAP:
            logger.warning(
                "[%d] Unrecognised result: '%s' for test case '%s'",
                job.id,
                result,
                name,
            )
            return None
        try:
            test_case = TestCase(
                name=name,
                suite=suite,
                test_set=testset,
                result=TestCase.RESULT_MAP[result],
                metadata=metadata,
                measurement=measurement,
                units=units,
                start_log_line=starttc,
                end_log_line=endtc,
            )
        except decimal.InvalidOperation:
            logger.exception("[%d] Unable to create test case %s", job.id, name)
    return test_case


def testsuite_export_fields():
    """
    Keep this list in sync with the keys in export_testsuite
    :return: list of fields used in export_testsuite
    """
    return ["name", "job", "id"]


def export_testsuite(testsuite):
    """
    Returns string versions of selected elements of a TestSuite
    :param testsuite: TestSuite object
    :return: Dictionary containing relevant information formatted for export
    """
    suitedict = {
        "name": str(testsuite.name),
        "job": str(testsuite.job_id),
        "id": str(testsuite.id),
    }
    return suitedict
