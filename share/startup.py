#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  Startup.py
#
#  Copyright 2014 Linaro Limited
#  Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

#
# Pre install some usefull tools when stating a python script with:
# PYTHONSTARTUP=./share/startup.py python
#
import django
from dashboard_app.models import *
from lava_scheduler_app.models import *
from linaro_django_xmlrpc.models import *
from django.db import transaction
print("=============================")
print("Startup script for LAVA")


print(" - Entering transaction mode")
transaction.set_autocommit(False)

print(" - creating rollback function")


def rollback():
    transaction.rollback()
print("=============================")
