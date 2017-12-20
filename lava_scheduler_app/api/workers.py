# Copyright (C) 2017 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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
# along with Lava Server.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys

from django.db import IntegrityError, transaction

from linaro_django_xmlrpc.models import ExposedV2API
from lava_scheduler_app.api import check_superuser
from lava_scheduler_app.models import Worker

if sys.version_info[0] == 2:
    # Python 2.x
    import xmlrpclib
elif sys.version_info[0] == 3:
    # For Python 3.0 and later
    import xmlrpc.client as xmlrpclib


class SchedulerWorkersAPI(ExposedV2API):

    @check_superuser
    def add(self, hostname, description=None, disabled=False):
        """
        Name
        ----
        `scheduler.workers.add` (`hostname`, `description=None`, `disabled=False`)

        Description
        -----------
        [superuser only]
        Add a new worker entry to the database.

        Arguments
        ---------
        `hostname`: string
          The name of the worker
        `description`: string
          Description of the worker
        `disabled`: bool
          Is the worker disabled?

        Return value
        ------------
        None
        """
        try:
            health = Worker.HEALTH_RETIRED if disabled else Worker.HEALTH_ACTIVE
            Worker.objects.create(hostname=hostname,
                                  description=description,
                                  health=health)
        except IntegrityError as exc:
            raise xmlrpclib.Fault(
                400, "Bad request: %s" % exc.message)

    def get_config(self, hostname):
        """
        Name
        ----
        `scheduler.workers.get_config` (`hostname`)

        Description
        -----------
        Return the worker configuration

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker

        Return value
        ------------
        This function returns the worker configuration
        """
        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Worker '%s' was not found." % hostname)

        filename = os.path.join("/etc/lava-server/dispatcher.d",
                                "%s.yaml" % hostname)
        try:
            with open(filename, "r") as f_in:
                return xmlrpclib.Binary(f_in.read().encode('utf-8'))
        except IOError:
            raise xmlrpclib.Fault(
                404, "Worker '%s' does not have a configuration" % hostname)

    @check_superuser
    def set_config(self, hostname, config):
        """
        Name
        ----
        `scheduler.workers.set_config` (`hostname`, `config`)

        Description
        -----------
        [superuser only]
        Set the worker configuration

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker
        `config`: string
          The worker configuration as a yaml file

        Return value
        ------------
        True if the configuration was saved to file, False otherwise.
        """
        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Worker '%s' was not found." % hostname)

        filename = os.path.join("/etc/lava-server/dispatcher.d",
                                "%s.yaml" % hostname)
        try:
            with open(filename, "w") as f_out:
                f_out.write(config)
                return True
        except IOError:
            return False

    def list(self):
        """
        Name
        ----
        `scheduler.workers.list` ()

        Description
        -----------
        List workers

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array of workers
        """
        workers = Worker.objects.all().order_by('hostname')
        return [w.hostname for w in workers]

    def show(self, hostname):
        """
        Name
        ----
        `scheduler.workers.show` (`hostname`)

        Description
        -----------
        Show some details about the given worker.

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker

        Return value
        ------------
        This function returns an XML-RPC dictionary with worker details
        """

        try:
            worker = Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpclib.Fault(
                404, "Worker '%s' was not found." % hostname)

        return {"hostname": worker.hostname,
                "description": worker.description,
                "state": worker.get_state_display(),
                "health": worker.get_health_display(),
                "devices": [d.hostname for d in worker.device_set.all().order_by("hostname")],
                "last_ping": worker.last_ping}

    @check_superuser
    def update(self, hostname, description=None, health=None):
        """
        Name
        ----
        `scheduler.workers.update` (`hostname`, `description=None`, `health=None`)

        Description
        -----------
        [superuser only]
        Update worker parameters

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker
        `description`: string
          Description of the worker
        `health`: string
          Set worker health ("ACTIVE", "MAINTENANCE" or "RETIRED")

        Return value
        ------------
        None
        """
        with transaction.atomic():
            try:
                worker = Worker.objects.select_for_update().get(hostname=hostname)
            except Worker.DoesNotExist:
                raise xmlrpclib.Fault(
                    404, "Worker '%s' was not found." % hostname)

            if description is not None:
                worker.description = description

            if health is not None:
                if health == "ACTIVE":
                    worker.go_health_active(self.user)
                elif health == "MAINTENANCE":
                    worker.go_health_maintenance(self.user)
                elif health == "RETIRED":
                    worker.go_health_retired(self.user)
                else:
                    raise xmlrpclib.Fault(
                        400, "Invalid health: %s" % health)

            worker.save()
