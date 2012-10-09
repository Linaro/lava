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

import time

from lava_dispatcher.signals import PerTestCaseSignalHandler


class signal_ni_bat_sim(PerTestCaseSignalHandler):

    def start_test_case(self, case_data):
        case_data['start'] = time.time()

    def stop_test_case(self, case_data):
        case_data['end'] = time.time()

    def postprocess_bundle(self, result, case_data):
        attrs = result.setdefault('attributes', {})
        attrs['duration'] = case_data['end'] - case_data['start']
