# Copyright (C) 2015 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of Lava Server.
#
# Lava Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# Lava Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Lava Dashboard.  If not, see <http://www.gnu.org/licenses/>.


from lava_results_app.models import TestSuite, TestCase
from lava.utils.lavatable import LavaView


class ResultsView(LavaView):
    """
    Base results view
    """
    def get_queryset(self):
        return TestSuite.objects.all().order_by('-job__id')


class SuiteView(LavaView):
    """
    View of a test suite
    """
    def get_queryset(self):
        return TestCase.objects.all().order_by('logged')
