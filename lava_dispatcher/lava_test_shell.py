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
import json
import logging
import re
import tarfile

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
    devices = _get_cpus(cpuinfo)
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


def _get_attachments(tarfile, dirname, testdef, stdout):
    files = ('stderr.log', 'return_code', 'run.sh')
    attachments = []

    attachments.append(create_attachment('stdout.txt', stdout))
    attachments.append(create_attachment('testdef.json', testdef))

    for f in files:
        buf = _get_content(tarfile, '%s/%s' % (dirname, f), ignore_errors=True)
        if buf:
            attachments.append(create_attachment(f, buf))

    return attachments


def _get_test_run(tarfile, dirname, hwcontext, swcontext):
    now = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    testdef = _get_content(tarfile, '%s/testdef.json' % dirname)
    stdout = _get_content(tarfile, '%s/stdout.log' % dirname)
    attachments = _get_attachments(tarfile, dirname, testdef, stdout)

    testdef = json.loads(testdef)

    return {
        'test_id': testdef['test_id'],
        'analyzer_assigned_date': now,
        'analyzer_assigned_uuid': str(uuid4()),
        'time_check_performed': False,
        'test_results': _get_test_results(testdef, stdout),
        'software_context': swcontext,
        'hardware_context': hwcontext,
        'attachments': attachments,
    }


def _get_content(tarfile, membername, ignore_errors=False):
    try:
        tinfo = tarfile.getmember(membername)
        f = tarfile.extractfile(tinfo)
        c = f.read()
        f.close()
        return c
    except:
        if ignore_errors:
            return ''
        else:
            raise


def get_bundle(lava_test_shell_tarball, sw_sources):
    ''' takes a tarball of the contents of the lava-test-shell data directory
    and returns a dashboard bundle
    '''
    testruns = []
    with tarfile.open(lava_test_shell_tarball) as tar:
        cpuinfo = _get_content(tar, './cpuinfo.txt')
        meminfo = _get_content(tar, './meminfo.txt')
        hwctx = _get_hw_context(cpuinfo, meminfo)

        build = _get_content(tar, './build.txt')
        pkginfo = _get_content(tar, './pkgs.txt', ignore_errors=True)
        swctx = _get_sw_context(build, pkginfo, sw_sources)

        for tinfo in tar:
            if tinfo.isdir() and tinfo.name != '.':
                testruns.append(_get_test_run(tar, tinfo.name, hwctx, swctx))

    return {'test_runs': testruns, 'format': 'Dashboard Bundle Format 1.3'}
