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
import json
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


def _get_test_results(testdef, stdout):
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
            results.append(res)

    return results


def _get_attachments(results_dir, dirname, testdef, stdout):
    files = ('stderr.log', 'return_code', 'run.sh', 'install.sh')
    attachments = []

    attachments.append(create_attachment('stdout.log', stdout))
    attachments.append(create_attachment('testdef.yaml', testdef))

    for f in files:
        fname = '%s/%s' % (dirname, f)
        buf = _get_content(results_dir, fname, ignore_errors=True)
        if buf:
            attachments.append(create_attachment(f, buf))

    return attachments


def _get_test_run(results_dir, dirname, hwcontext, swcontext):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    testdef = _get_content(results_dir, '%s/testdef.yaml' % dirname)
    stdout = _get_content(results_dir, '%s/stdout.log' % dirname)
    attachments = _get_attachments(results_dir, dirname, testdef, stdout)

    testdef = yaml.load(testdef)

    return {
        'test_id': testdef.get('metadata').get('name'),
        'analyzer_assigned_date': now,
        'analyzer_assigned_uuid': str(uuid4()),
        'time_check_performed': False,
        'test_results': _get_test_results(testdef, stdout),
        'software_context': swcontext,
        'hardware_context': hwcontext,
        'attachments': attachments,
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

    for d in os.listdir(results_dir):
        if os.path.isdir(os.path.join(results_dir, d)):
            try:
                testruns.append(_get_test_run(results_dir, d, hwctx, swctx))
            except:
                logging.exception('error processing results for: %s' % d)

    return {'test_runs': testruns, 'format': 'Dashboard Bundle Format 1.3'}
