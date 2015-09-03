# Copyright (C) 2013 Linaro Limited
#
# Author: Tyler Baker <tyler.baker@linaro.org>
#         Arthur She <arthur.she@linaro.org>
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
# along with this program; if not, see <http://www.gnu.org/licenses>.

import logging
import tempfile
import re
import os
import pexpect

from uuid import uuid4
from lava_dispatcher.actions import BaseAction
from lava_dispatcher.bundle import PrettyPrinter
from lava_dispatcher.errors import OperationFailed
from linaro_dashboard_bundle.io import DocumentIO
from lava_dispatcher.test_data import create_attachment
from lava_dispatcher.utils import read_content
from datetime import datetime


class cmd_lava_command_run(BaseAction):

    parameters_schema = {
        'type': 'object',
        'properties': {
            'commands': {'type': 'array', 'items': {'type': 'string'},
                         'optional': False},
            'parser': {'type': 'string', 'optional': True},
            'fixupdict': {'type': 'array', 'items': {'type': 'string'},
                          'optional': True},
            'iterations': {'type': 'integer', 'optional': True},
            'role': {'type': 'string', 'optional': True},
            'timeout': {'type': 'integer', 'optional': True},
        },
        'additionalProperties': False,
    }
    _logfile = ""
    _parser = None
    _fixupdict = {}
    _results_from_log_file = []

    def run(self, commands, parser=None, iterations=1, fixupdict=None, timeout=-1):
        target = self.client.target_device
        log_dir = tempfile.mkdtemp(dir=target.scratch_dir)
        self._logfile = os.path.join(log_dir, 'stdout.log')
        if parser is not None:
            self._parser = parser
        if fixupdict is not None:
            self._fixupdict = fixupdict
        logging.info("lava_command logfile: %s" % self._logfile)
        with self.client.tester_session() as session:
            for count in range(iterations):
                logging.info("Executing lava_command_run iteration: %s" % count)
                for command in commands:
                    logging.info("Executing lava_command_run: %s" % command)
                    try:
                        res = {}
                        res['test_case_id'] = command
                        session.run(command, timeout=timeout,
                                    log_in_host=self._logfile)
                        res['result'] = 'pass'
                        self._results_from_log_file.append(res)
                    except (OperationFailed, RuntimeError, pexpect.TIMEOUT) as e:
                        res['result'] = 'fail'
                        self._results_from_log_file.append(res)
                        logging.error(e)

        bundle = self._get_bundle()
        self._write_results_bundle(bundle)

        printer = PrettyPrinter(self.context)
        printer.print_results(bundle)

    def _read_fixupdict(self):
        fdict = {}
        if self._fixupdict is not None:
            for e in self._fixupdict:
                k, v = e.split(':')
                fdict.update({k.strip(): v.strip()})

        return fdict

    def _get_test_results(self):
        fixupdict = {}
        defpat = "(?P<test_case_id>.*-*)\\s+:\\s+(?P<result>(PASS|pass|FAIL|fail|SKIP|skip|UNKNOWN|unknown))"
        if self._parser is not None:
            pattern = re.compile(self._parser)
            fixupdict = self._read_fixupdict()
        else:
            pattern = re.compile(defpat)
            logging.warning("""Using a default pattern to parse the test result. This may lead to empty test result in certain cases.""")

        logfile = read_content(self._logfile)
        for lineno, line in enumerate(logfile.split('\n'), 1):
            match = pattern.match(line.strip())
            if match:
                res = match.groupdict()
                if 'result' in res:
                    if res['result'] in fixupdict:
                        res['result'] = fixupdict[res['result']]
                    if res['result'] not in ('pass', 'fail', 'skip', 'unknown'):
                        logging.error('bad test result line: %s' % line.strip())
                        continue
                res['log_lineno'] = lineno
                res['log_filename'] = os.path.basename(self._logfile)

                self._results_from_log_file.append(res)

        return self._results_from_log_file

    def _get_test_runs(self):
        now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        attachment = [create_attachment(os.path.basename(self._logfile), read_content(self._logfile))]
        results = self._get_test_results()
        return {
            'test_id': 'lava-command',
            'analyzer_assigned_date': now,
            'analyzer_assigned_uuid': str(uuid4()),
            'time_check_performed': False,
            'test_results': results,
            'attachments': attachment
        }

    def _get_bundle(self):
        return {
            'test_runs': [self._get_test_runs()],
            'format': 'Dashboard Bundle Format 1.7.1'
        }

    def _write_results_bundle(self, bundle):
        rdir = self.context.host_result_dir
        (fd, name) = tempfile.mkstemp(
            prefix='lava-command', suffix='.bundle', dir=rdir)
        with os.fdopen(fd, 'w') as f:
            DocumentIO.dump(f, bundle)
