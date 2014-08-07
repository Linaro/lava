# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of linaro-django-xmlrpc.
#
# linaro-django-xmlrpc is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# linaro-django-xmlrpc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with linaro-django-xmlrpc.  If not, see <http://www.gnu.org/licenses/>.

"""
Global objects
"""

from linaro_django_xmlrpc.models import Mapper


mapper = Mapper()
mapper.register_introspection_methods()
