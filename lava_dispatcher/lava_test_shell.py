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
import decimal
import mimetypes
import yaml
import logging
import os
import re

from lava_dispatcher.test_data import create_attachment


def _get_cpus(cpuinfo):
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
        elif key == 'processor':
            cpu_cores += 1
        elif key == 'Hardware':
            board_type = val
        elif key == 'Revision':
            board_rev = val
        else:
            cpu_attrs[key] = val

    cpu_attrs['cpu_type'] = cpu_type

    for i in xrange(cpu_cores):
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
    ctx = {}
    ctx['image'] = {'name': build}

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


def _attachments_from_dir(dir):
    attachments = []
    for filename, filepath in _directory_names_and_paths(dir, ignore_missing=True):
        if filename.endswith('.mimetype'):
            continue
        mime_type = _read_content(filepath + '.mimetype', ignore_missing=True).strip()
        if not mime_type:
            mime_type = mimetypes.guess_type(filepath)[0]
            if mime_type is None:
                mime_type = 'application/octet-stream'
        attachments.append(
            create_attachment(filename, _read_content(filepath), mime_type))
    return attachments


def _attributes_from_dir(dir):
    attributes = {}
    for filename, filepath in _directory_names_and_paths(dir, ignore_missing=True):
        if os.path.isfile(filepath):
            attributes[filename] = _read_content(filepath)
    return attributes


def _result_to_dir(test_result, dir):

    def w(name, content):
        with open(os.path.join(dir, name), 'w') as f:
            f.write(str(content) + '\n')

    for name in 'result', 'measurement', 'units', 'message', 'timestamp', 'duration':
        if name in test_result:
            w(name, test_result[name])


    os.makedirs(os.path.join(dir, 'attachments'))

    for attachment in test_result.get('attachments', []):
        path = 'attachments/' + attachment['pathname']
        w(path, base64.b64decode(attachment['content']))
        w(path + '.mimetype', attachment['mime_type'])

    os.makedirs(os.path.join(dir, 'attributes'))

    for attrname, attrvalue in test_result.get('attributes', []).items():
        path = 'attributes/' + attrname
        w(path, attrvalue)


def _result_from_dir(dir):
    result = {
        'test_case_id': os.path.basename(dir),
        }

    for fname in 'result', 'measurement', 'units', 'message', 'timestamp', 'duration':
        fpath = os.path.join(dir, fname)
        if os.path.isfile(fpath):
            result[fname] = _read_content(fpath).strip()

    if 'measurement' in result:
        try:
            result['measurement'] = decimal.Decimal(result['measurement'])
        except decimal.InvalidOperation:
            logging.warning("Invalid measurement for %s: %s" % (dir, result['measurement']))
            del result['measurement']

    result['attachments'] = _attachments_from_dir(os.path.join(dir, 'attachments'))
    result['attributes'] = _attributes_from_dir(os.path.join(dir, 'attributes'))

    return result


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
                dest[attrname] = src
    dest.setdefault('attachments', []).extend(src.get('attachments', []))
    dest.setdefault('attributes', {}).update(src.get('attributes', []))


def _get_test_results(test_run_dir, testdef, stdout):
    results_from_log_file = []
    fixupdict = {}

    if 'parse' in testdef:
        if 'fixupdict' in testdef['parse']:
            fixupdict = testdef['parse']['fixupdict']
        if 'pattern' in testdef['parse']:
            pattern = re.compile(testdef['parse']['pattern'])
    else:
        defpat = "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))"
        pattern = re.compile(defpat)
        fixupdict = {'PASS': 'pass', 'FAIL': 'fail', 'SKIP': 'skip',
                     'UNKNOWN': 'unknown'}
        logging.warning("""Using a default pattern to parse the test result. This may lead to empty test result in certain cases.""")

    for line in stdout.split('\n'):
        match = pattern.match(line.strip())
        if match:
            res = match.groupdict()
            if 'result' in res:
                if res['result'] in fixupdict:
                    res['result'] = fixupdict[res['result']]
                if res['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                    logging.error('bad test result line: %s' % line.strip())
                    continue

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

    return results_from_log_file


def _get_run_attachments(test_run_dir, testdef, stdout):
    attachments = []

    attachments.append(create_attachment('stdout.log', stdout))
    attachments.append(create_attachment('testdef.yaml', testdef))
    return_code = _read_content(os.path.join(test_run_dir, 'return_code'), ignore_missing=True)
    if return_code:
        attachments.append(create_attachment('return_code', return_code))

    attachments.extend(
        _attachments_from_dir(os.path.join(test_run_dir, 'attachments')))

    return attachments


def _get_test_run(test_run_dir, hwcontext, build, pkginfo, testdefs_by_uuid):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    testdef = _read_content(os.path.join(test_run_dir, 'testdef.yaml'))
    stdout = _read_content(os.path.join(test_run_dir, 'stdout.log'))
    uuid = _read_content(os.path.join(test_run_dir, 'analyzer_assigned_uuid'))
    attachments = _get_run_attachments(test_run_dir, testdef, stdout)
    attributes = _attributes_from_dir(os.path.join(test_run_dir, 'attributes'))

    testdef = yaml.load(testdef)
    if uuid in testdefs_by_uuid:
        sw_sources = testdefs_by_uuid[uuid]._sw_sources
    else:
        sw_sources = []
    swcontext = _get_sw_context(build, pkginfo, sw_sources)

    return {
        'test_id': testdef.get('metadata').get('name'),
        'analyzer_assigned_date': now,
        'analyzer_assigned_uuid': uuid,
        'time_check_performed': False,
        'test_results': _get_test_results(test_run_dir, testdef, stdout),
        'software_context': swcontext,
        'hardware_context': hwcontext,
        'attachments': attachments,
        'attributes': attributes,
    }


def _read_content(filepath, ignore_missing=False):
    if not os.path.exists(filepath) and ignore_missing:
        return ''
    with open(filepath, 'r') as f:
        return f.read()


def _directory_names_and_paths(dirpath, ignore_missing=False):
    if not os.path.exists(dirpath) and ignore_missing:
        return []
    return [(filename, os.path.join(dirpath, filename))
            for filename in os.listdir(dirpath)]


def get_bundle(results_dir, testdefs_by_uuid):
    """
    iterates through a results directory to build up a bundle formatted for
    the LAVA dashboard
    """
    testruns = []
    cpuinfo = _read_content(os.path.join(results_dir, 'hwcontext/cpuinfo.txt'), ignore_missing=True)
    meminfo = _read_content(os.path.join(results_dir, 'hwcontext/meminfo.txt'), ignore_missing=True)
    hwctx = _get_hw_context(cpuinfo, meminfo)

    build = _read_content(os.path.join(results_dir, 'swcontext/build.txt'))
    pkginfo = _read_content(os.path.join(results_dir, 'swcontext/pkgs.txt'), ignore_missing=True)

    for test_run_name, test_run_path in _directory_names_and_paths(results_dir):
        if test_run_name in ('hwcontext', 'swcontext'):
            continue
        if os.path.isdir(test_run_path):
            try:
                testruns.append(_get_test_run(test_run_path, hwctx, build, pkginfo, testdefs_by_uuid))
            except:
                logging.exception('error processing results for: %s' % test_run_name)

    return {'test_runs': testruns, 'format': 'Dashboard Bundle Format 1.5'}
