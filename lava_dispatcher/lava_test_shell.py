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

import datetime
import errno
import mimetypes
import yaml
import logging
import os
import re

from uuid import uuid4

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
    for filename in os.listdir(dir):
        if filename.endswith('.mimetype'):
            continue
        filepath = os.path.join(dir, filename)
        if os.path.exists(filepath + '.mimetype'):
            mime_type = open(filepath + '.mimetype').read().strip()
        else:
            mime_type = mimetypes.guess_type(filepath)[0]
            if mime_type is None:
                mime_type = 'application/octet-stream'
        attachments.append(
            create_attachment(filename, open(filepath).read(), mime_type))


def _attributes_from_dir(dir):
    attributes = {}
    for filename in os.listdir(dir):
        filepath = os.path.join(dir, filename)
        if os.path.isfile(filepath):
            attributes[filename] = open(filepath).read()


def _get_test_results(test_run_dir, testdef, stdout):
    results = []

    pattern = re.compile(testdef['parse']['pattern'])

    fixupdict = {}
    if 'fixupdict' in testdef['parse']:
        fixupdict = testdef['parse']['fixupdict']

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
            tc_id = res.get('test_case_id')
            if tc_id is not None:
                d = os.path.join(test_run_dir, 'results', tc_id, 'attachments')
                if os.path.isdir(d):
                    res['attachments'] = _attachments_from_dir(d)
                d = os.path.join(test_run_dir, 'results', tc_id, 'attributes')
                if os.path.isdir(d):
                    res['attributes'] = _attributes_from_dir(d)

            results.append(res)

    return results


def _get_run_attachments(results_dir, test_run_dir, testdef, stdout):
    attachments = []

    attachments.append(create_attachment('stdout.log', stdout))
    attachments.append(create_attachment('testdef.yaml', testdef))
    return_code_file = os.path.join(results_dir, 'return_code')
    if os.path.exists(return_code_file):
        attachments.append(create_attachment('return_code', open(return_code_file).read()))

    attachments.extend(
        _attachments_from_dir(os.path.join(results_dir, 'attachments')))

    return attachments


def _get_test_run(results_dir, test_run_dir, hwcontext, swcontext):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    testdef = _get_content(results_dir, '%s/testdef.yaml' % test_run_dir)
    stdout = _get_content(results_dir, '%s/stdout.log' % test_run_dir)
    attachments = _get_run_attachments(results_dir, test_run_dir, testdef, stdout)
    attributes = _attributes_from_dir('%s/attributes' % test_run_dir)

    testdef = yaml.load(testdef)

    return {
        'test_id': testdef.get('metadata').get('name'),
        'analyzer_assigned_date': now,
        'analyzer_assigned_uuid': str(uuid4()),
        'time_check_performed': False,
        'test_results': _get_test_results(test_run_dir, testdef, stdout),
        'software_context': swcontext,
        'hardware_context': hwcontext,
        'attachments': attachments,
        'attributes': attributes,
    }


def _get_content(results_dir, fname, ignore_errors=False):
    try:
        with open(os.path.join(results_dir, fname), 'r') as f:
            return f.read()
    except IOError as e:
        if e.errno != errno.ENOENT or not ignore_errors:
            logging.exception('Error while reading %s' % fname)
        if ignore_errors:
            return ''


def get_bundle(results_dir, sw_sources):
    """
    iterates through a results directory to build up a bundle formatted for
    the LAVA dashboard
    """
    testruns = []
    cpuinfo = _get_content(results_dir, './cpuinfo.txt', ignore_errors=True)
    meminfo = _get_content(results_dir, './meminfo.txt', ignore_errors=True)
    hwctx = _get_hw_context(cpuinfo, meminfo)

    build = _get_content(results_dir, './build.txt')
    pkginfo = _get_content(results_dir, './pkgs.txt', ignore_errors=True)
    swctx = _get_sw_context(build, pkginfo, sw_sources)

    for test_run_dir in os.listdir(results_dir):
        if os.path.isdir(os.path.join(results_dir, test_run_dir)):
            try:
                testruns.append(_get_test_run(results_dir, test_run_dir, hwctx, swctx))
            except:
                logging.exception('error processing results for: %s' % test_run_dir)

    return {'test_runs': testruns, 'format': 'Dashboard Bundle Format 1.5'}
