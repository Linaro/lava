# Copyright (C) 2011-2012 Linaro Limited
#
# Author: Andy Doan <andy.doan@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

"""
Import test results from disk.

This module contains functions to create a bundle from the disk files created
by a lava-test-shell run.
"""

import base64
import datetime
import mimetypes
import yaml
import logging
import os
import re
import fnmatch

from lava_dispatcher.test_data import create_attachment
from lava_dispatcher.utils import read_content, write_content


def _get_cpus(cpuinfo):
    """
    Parse cpuinfo for data about the device
    Where Processor is not found, use model name.
    Where Hardware is not found, use vendor_id
    The cpu_type will be used as the device CPU type.
    The board_type will be used as the device description.
    :param cpuinfo: output of /proc/cpuinfo
    :return: a list of device data fields
    """
    devices = []
    cpu_type = '?'
    cpu_cores = 0
    cpu_attrs = {}
    board_type = '?'
    board_rev = '?'
    for line in cpuinfo.split('\n'):
        if len(line.strip()) == 0:
            continue
        (key, val) = line.split(':', 1)
        key = key.strip()
        val = val.strip()

        if key == 'Processor':
            cpu_type = val
        elif key == "model name":
            cpu_type = val
        elif key == 'processor':
            cpu_cores += 1
        elif key == 'Hardware':
            board_type = val
        elif key == "vendor_id":
            board_type = val
        elif key == 'Revision':
            board_rev = val
        else:
            cpu_attrs[key] = val

    cpu_attrs['cpu_type'] = cpu_type

    for i in range(cpu_cores):
        x = {
            'device_type': 'device.cpu',
            'description': 'Processor #%d' % i,
            'attributes': cpu_attrs
        }
        devices.append(x)

    devices.append({
        'device_type': 'device.board',
        'description': board_type,
        'attributes': {'revision': board_rev}
    })

    return devices


def _get_mem(meminfo):
    for line in meminfo.split('\n'):
        if line.startswith('MemTotal'):
            (k, v) = line.split(':', 1)
            return {
                'device_type': 'device.mem',
                'description': '%s of RAM' % v.strip(),
            }

    return None


def _get_hw_context(cpuinfo, meminfo):
    devices = []
    if cpuinfo:
        devices.extend(_get_cpus(cpuinfo))
    if meminfo:
        devices.append(_get_mem(meminfo))
    return {'devices': devices}


def _get_sw_context(build, pkgs, sw_sources):
    ctx = {'image': {'name': build}}

    pkglist = []
    pattern = re.compile(
        ("^\s*package:\s*(?P<package_name>[^:]+?)\s*:"
         "\s*(?P<version>[^\s].+)\s*$"), re.M)
    for line in pkgs.split('\n'):
        match = pattern.search(line)
        if match:
            name, version = match.groups()
            pkglist.append({'name': name.strip(), 'version': version})

    ctx['packages'] = pkglist
    ctx['sources'] = sw_sources
    return ctx


def _attachments_from_dir(from_dir):
    attachments = []
    if from_dir:
        for dirpath, dirnames, filenames in os.walk(from_dir):
            for f in filenames:
                if f.endswith('.mimetype'):
                    continue
                filepath = os.path.join(dirpath, f)
                mime_type = read_content(filepath + '.mimetype', ignore_missing=True).strip()
                if not mime_type:
                    mime_type = mimetypes.guess_type(filepath)[0]
                    if mime_type is None:
                        mime_type = 'application/octet-stream'
                filename = filepath[len(from_dir) + 1:]
                attachments.append(
                    create_attachment(filename, read_content(filepath), mime_type))

    return attachments


def _attributes_from_dir(from_dir):
    attributes = {}
    for filename, filepath in _directory_names_and_paths(from_dir, ignore_missing=True):
        if os.path.isfile(filepath):
            attributes[filename] = read_content(filepath)
    return attributes


def _result_to_dir(test_result, res_dir):

    def w(name, content):
        with open(os.path.join(res_dir, name), 'w') as f:
            f.write(str(content) + '\n')

    for name in 'result', 'measurement', 'units', 'message', 'timestamp', 'duration':
        if name in test_result:
            w(name, test_result[name])

    os.makedirs(os.path.join(res_dir, 'attachments'))

    for attachment in test_result.get('attachments', []):
        path = 'attachments/' + attachment['pathname']
        w(path, base64.b64decode(attachment['content']))
        w(path + '.mimetype', attachment['mime_type'])

    os.makedirs(os.path.join(res_dir, 'attributes'))

    for attrname, attrvalue in test_result.get('attributes', []).items():
        path = 'attributes/' + attrname
        w(path, attrvalue)


def _result_from_dir(res_dir, test_case_id=None):
    data = {}
    test_run_dir = os.path.dirname(res_dir)

    for fname in 'result', 'measurement', 'units', 'message', 'timestamp', 'duration':
        for path, dirs, files in os.walk(os.path.abspath(res_dir)):
            for filename in fnmatch.filter(files, fname):
                fpath = os.path.join(path, filename)
                if os.path.isfile(fpath):
                    data['test_case_id'] = os.path.relpath(path, test_run_dir)
                    data[fname] = read_content(fpath).strip()

    result = parse_testcase_result(data)

    result['attachments'] = _attachments_from_dir(os.path.join(res_dir, 'attachments'))
    result['attributes'] = _attributes_from_dir(os.path.join(res_dir, 'attributes'))

    return result


def parse_testcase_result(data, fixupdict={}):
    res = {}
    for key in data:
        res[key] = data[key]

        if key == 'measurement':
            # Measurement accepts non-numeric values, but be careful with
            # special characters including space, which may distrupt the
            # parsing.
            res[key] = res[key]

        elif key == 'result':
            if res['result'] in fixupdict:
                res['result'] = fixupdict[res['result']]
            if res['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                logging.error('Bad test result: %s', res['result'])
                res['result'] = 'unknown'

    if 'test_case_id' not in res:
        logging.warning(
            """Test case results without test_case_id (probably a sign of an """
            """incorrect parsing pattern being used): %s""", res)

    if 'result' not in res:
        logging.warning(
            """Test case results without result (probably a sign of an """
            """incorrect parsing pattern being used): %s""", res)
        logging.warning('Setting result to "unknown"')
        res['result'] = 'unknown'

    return res


def _merge_results(dest, src):
    tc_id = dest['test_case_id']
    assert tc_id == src['test_case_id']
    for attrname in 'result', 'measurement', 'units', 'message', 'timestamp', 'duration':
        if attrname in dest:
            if attrname in src:
                if dest[attrname] != src[attrname]:
                    logging.warning(
                        'differing values for %s in result for %s: %s and %s',
                        attrname, tc_id, dest[attrname], src[attrname])
        else:
            if attrname in src:
                dest[attrname] = src[attrname]
    dest.setdefault('attachments', []).extend(src.get('attachments', []))
    dest.setdefault('attributes', {}).update(src.get('attributes', []))


def _get_test_results(test_run_dir, testdef, stdout, err_log):
    results_from_log_file = []
    fixupdict = {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'skip',
                 'UNKNOWN': 'unknown'}
    pattern = None
    pattern_used = None

    return_code = read_content(os.path.join(test_run_dir, 'install_return_code'), ignore_missing=True)
    if return_code:
        code = int(return_code)
        res = {}
        res['test_case_id'] = 'lava-test-shell-install'
        if code == 0:
            res['result'] = 'pass'
        else:
            res['result'] = 'fail'
        res['message'] = 'exit code ' + return_code
        results_from_log_file.append(res)

    if 'parse' in testdef:
        if 'fixupdict' in testdef['parse']:
            fixupdict.update(testdef['parse']['fixupdict'])
        if 'pattern' in testdef['parse']:
            pattern_used = testdef['parse']['pattern']
    else:
        defpat = "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))"
        pattern_used = defpat
        logging.warning("""Using a default pattern to parse the test result. This may lead to empty test result in certain cases.""")

    try:
        pattern = re.compile(pattern_used)
    except re.error as e:
        errmsg = "Pattern '{0:s}' for test run '{1:s}' compile error ({2:s}). "
        errmsg = errmsg.format(pattern_used, testdef['metadata']['name'], str(e))
        write_content(err_log, errmsg)
        return results_from_log_file

    if not pattern:
        logging.debug("No pattern set")

    slim_pattern = "<LAVA_SIGNAL_TESTCASE TEST_CASE_ID=(?P<test_case_id>.*)\\s+"\
                   "RESULT=(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))>"

    test_pattern = "<LAVA_SIGNAL_TESTCASE TEST_CASE_ID=(?P<test_case_id>.*)\\s+"\
                   "RESULT=(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))\\s"\
                   "UNITS=(?P<units>.*)\s"\
                   "MEASUREMENT=(?P<measurement>.*)>"
    test_case_pattern = re.compile(test_pattern)
    result_pattern = re.compile(slim_pattern)

    for lineno, line in enumerate(stdout.split('\n'), 1):
        match = pattern.match(line.strip())
        if match:
            res = parse_testcase_result(match.groupdict(), fixupdict)
            # Both of 'test_case_id' and 'result' must be included
            if 'test_case_id' not in res or 'result' not in res:
                errmsg = "Pattern '{0:s}' for test run '{1:s}' is missing test_case_id or result. "
                errmsg = errmsg.format(pattern_used, testdef['metadata']['name'])
                write_content(err_log, errmsg)
                return results_from_log_file
            res['log_lineno'] = lineno
            res['log_filename'] = 'stdout.log'
            results_from_log_file.append(res)
            continue
        # Locate a simple lava-test-case with result to retrieve log line no
        match = result_pattern.match(line.strip())
        if match:
            res = parse_testcase_result(match.groupdict(), fixupdict)
            res['log_lineno'] = lineno
            res['log_filename'] = 'stdout.log'
            results_from_log_file.append(res)
            continue
        # also catch a lava-test-case with a unit and a measurement
        match = test_case_pattern.match(line.strip())
        if match:
            res = parse_testcase_result(match.groupdict(), fixupdict)
            res['log_lineno'] = lineno
            res['log_filename'] = 'stdout.log'
            results_from_log_file.append(res)

    results_from_directories = []
    results_from_directories_by_id = {}

    result_names_and_paths = _directory_names_and_paths(
        os.path.join(test_run_dir, 'results'), ignore_missing=True)
    result_names_and_paths = [
        (name, path) for (name, path) in result_names_and_paths
        if os.path.isdir(path)]
    result_names_and_paths.sort(key=lambda (name, path): os.path.getmtime(path))

    for name, path in result_names_and_paths:
        r = _result_from_dir(path)
        results_from_directories_by_id[name] = (r, len(results_from_directories))
        results_from_directories.append(r)

    for res in results_from_log_file:
        if res.get('test_case_id') in results_from_directories_by_id:
            dir_res, index = results_from_directories_by_id[res['test_case_id']]
            results_from_directories[index] = None
            _merge_results(res, dir_res)

    for res in results_from_directories:
        if res is not None:
            results_from_log_file.append(res)

    return_code = read_content(os.path.join(test_run_dir, 'return_code'), ignore_missing=True)
    if return_code:
        code = int(return_code)
        res = {}
        res['test_case_id'] = 'lava-test-shell-run'
        if code == 0:
            res['result'] = 'pass'
        else:
            res['result'] = 'fail'
        res['message'] = 'exit code ' + return_code
        results_from_log_file.append(res)

    return results_from_log_file


def _get_run_attachments(test_run_dir, testdef, stdout):
    attachments = [create_attachment('stdout.log', stdout),
                   create_attachment('testdef.yaml', testdef)]
    return_code = read_content(os.path.join(test_run_dir, 'return_code'), ignore_missing=True)
    if return_code:
        attachments.append(create_attachment('return_code', return_code))

    attachments.extend(
        _attachments_from_dir(os.path.join(test_run_dir, 'attachments')))

    return attachments


def _get_run_testdef_metadata(test_run_dir):
    testdef_metadata = {
        'version': None,
        'description': None,
        'format': None,
        'location': None,
        'url': None,
        'os': None,
        'devices': None,
        'environment': None
    }

    metadata = read_content(os.path.join(test_run_dir, 'testdef_metadata'))
    if metadata is not '':
        testdef_metadata = yaml.safe_load(metadata)

    # Read extra metadata, if any. All metadata gets into testdef_metadata in
    # the bundle.
    extra_metadata = ''
    extra_metadata_path = os.path.join(test_run_dir, 'extra_metadata')
    if os.path.exists(extra_metadata_path):
        extra_metadata = read_content(extra_metadata_path)
    if extra_metadata is not '':
        extra_metadata = yaml.safe_load(extra_metadata)
        testdef_metadata.update(extra_metadata)

    return testdef_metadata


def get_testdef_obj_with_uuid(testdef_objs, uuid):
    """Returns a single testdef object which has the given UUID from the list
    of TESTDEF_OBJS provided.
    """
    return (td for td in testdef_objs if td.uuid == uuid).next()


def _get_test_run(test_run_dir, testdef_objs, err_log):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    testdef = read_content(os.path.join(test_run_dir, 'testdef.yaml'))
    stdout = read_content(os.path.join(test_run_dir, 'stdout.log'))
    uuid = read_content(os.path.join(test_run_dir, 'analyzer_assigned_uuid'))

    cpuinfo = read_content(os.path.join(test_run_dir, 'hwcontext/cpuinfo.txt'), ignore_missing=True)
    meminfo = read_content(os.path.join(test_run_dir, 'hwcontext/meminfo.txt'), ignore_missing=True)
    hwcontext = _get_hw_context(cpuinfo, meminfo)

    build = read_content(os.path.join(test_run_dir, 'swcontext/build.txt'), ignore_missing=True)
    pkginfo = read_content(os.path.join(test_run_dir, 'swcontext/pkgs.txt'), ignore_missing=True)

    attachments = _get_run_attachments(test_run_dir, testdef, stdout)
    attributes = _attributes_from_dir(os.path.join(test_run_dir, 'attributes'))

    testdef = yaml.safe_load(testdef)

    testdef_obj = get_testdef_obj_with_uuid(testdef_objs, uuid)

    if testdef_obj:
        sw_sources = testdef_obj._sw_sources
    else:
        logging.warning("no software sources found for run with uuid %s", uuid)
        sw_sources = []
    swcontext = _get_sw_context(build, pkginfo, sw_sources)

    return {
        'test_id': testdef.get('metadata').get('name'),
        'analyzer_assigned_date': now,
        'analyzer_assigned_uuid': uuid,
        'time_check_performed': False,
        'test_results': _get_test_results(test_run_dir, testdef, stdout, err_log),
        'software_context': swcontext,
        'hardware_context': hwcontext,
        'attachments': attachments,
        'attributes': attributes,
        'testdef_metadata': _get_run_testdef_metadata(test_run_dir)
    }


def _directory_names_and_paths(dirpath, ignore_missing=False):
    if not os.path.exists(dirpath) and ignore_missing:
        return []
    return [(filename, os.path.join(dirpath, filename))
            for filename in os.listdir(dirpath)]


def get_bundle(results_dir, testdef_objs, err_log):
    """
    iterates through a results directory to build up a bundle formatted for
    the LAVA dashboard
    """
    testruns = []
    for test_run_name, test_run_path in _directory_names_and_paths(results_dir):
        if test_run_name in ('hwcontext', 'swcontext'):
            continue
        if os.path.isdir(test_run_path):
            try:
                testruns.append(_get_test_run(test_run_path, testdef_objs, err_log))
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                logging.exception('error processing results for: %s', test_run_name)

    return {'test_runs': testruns, 'format': 'Dashboard Bundle Format 1.7.1'}
