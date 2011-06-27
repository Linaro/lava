# Copyright (C) 2011 Linaro Limited
#
# Author: Linaro Validation Team <linaro-dev@lists.linaro.org>
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

import os
from uuid import uuid1
from datetime import datetime
import json
import subprocess
from lava_dispatcher.config import LAVA_RESULT_DIR
import time

# TODO: Result saving could be replaced by linaro_dashboard_bundle probably.
def savebundlefile(testname, results, starttime):
    """
    Save results as .bundle file under /tmp/LAVA_RESULT_DIR/
    """
    TIMEFORMAT = '%Y-%m-%dT%H:%M:%SZ'
    testdata = {}
    test_runs = [{}]
    testdata['format'] = "Dashboard Bundle Format 1.2"
    test_runs[0]['test_id'] = testname
    test_runs[0]['analyzer_assigned_uuid'] = str(uuid1())
    test_runs[0]['time_check_performed'] = False
    test_runs[0]['analyzer_assigned_date'] = starttime 
    # TODO: hw_context sw_context for android
    testdata['test_runs'] = test_runs
    testdata['test_runs'][0].update(results)
    bundle = testdata
    subprocess.call(["mkdir", "-p", "/tmp/%s" % LAVA_RESULT_DIR])
    # The file name should be unique to be distinguishable from others
    filename = "/tmp/%s/" % LAVA_RESULT_DIR + testname + \
        str(time.mktime(datetime.utcnow().timetuple())) + ".bundle"
    with open(filename, "wt") as stream:
        json.dump(bundle, stream)

