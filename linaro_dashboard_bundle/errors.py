# Copyright (C) 2010 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of linaro-dashboard-bundle.
#
# linaro-dashboard-bundle is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# linaro-dashboard-bundle is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with linaro-dashboard-bundle.  If not, see <http://www.gnu.org/licenses/>.


class DocumentFormatError(ValueError):
    """
    Exception raised when document format is not in the set of known
    values.

    You can access the :format: property to inspect the format that was
    found in the document
    """

    def __init__(self, format):
        self.format = format

    def __str__(self):
        return "Unrecognized or missing document format"
