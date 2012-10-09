#!/usr/bin/python

# Copyright (C) 2012 Linaro Limited
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

import logging

from lava_dispatcher.test_data import create_attachment
from lava_dispatcher.signals import BaseSignal


class signal_ni_bat_sim(BaseSignal):

    def on_test_run_start(self, action, testrun_idx, test_id):
        s = super(signal_ni_bat_sim, self)
        data = s.on_test_run_start(action, testrun_idx, test_id)
        data = (testrun_idx, test_id, data)
        action.add_bundle_helper(self._bundle_helper, data)

    def _bundle_helper(self, bundle, data):
        (testrun_idx, test_id, data) = data
        attachment = create_attachment(
            'ni_bat_sim', '%s: %r' % (test_id, data))
        bundle['test_runs'][testrun_idx]['attachments'].append(attachment)
