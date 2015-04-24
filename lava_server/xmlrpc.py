# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
# Author: Michael Hudson-Doyle <michael.hudson@linaro.org>
#
# This file is part of LAVA Server.
#
# LAVA Server is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA Server is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Server.  If not, see <http://www.gnu.org/licenses/>.

from linaro_django_xmlrpc.models import Mapper, SystemAPI


class LavaSystemAPI(SystemAPI):
    """
    Extend the default SystemAPI with a 'whoami' method.
    """

    def whoami(self):
        """
        Name
        ----
        `whoami` ()

        Description
        -----------
        Find the authenticated user, if any, or None.

        Arguments
        ---------
        None

        Return value
        ------------
        Name of the authenticated user, if any, or None.
        """
        if self.user:
            return self.user.username
        else:
            return None


class LavaMapper(Mapper):

    def register_introspection_methods(self):
        """
        Register LavaSystemAPI as 'system' object.

        LavaSystemAPI adds a 'whoami' system method above what the default
        has.
        """
        self.register(LavaSystemAPI, 'system')
