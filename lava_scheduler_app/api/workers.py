# -*- coding: utf-8 -*-
# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA.  If not, see <http://www.gnu.org/licenses/>.

import os
import xmlrpc.client

from django.db import IntegrityError, transaction

from linaro_django_xmlrpc.models import ExposedV2API
from lava_scheduler_app.api import check_perm
from lava_scheduler_app.models import Worker


class SchedulerWorkersAPI(ExposedV2API):
    @check_perm("lava_scheduler_app.add_worker")
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
            Worker.objects.create(
                hostname=hostname, description=description, health=health
            )
        except IntegrityError:
            raise xmlrpc.client.Fault(400, "Bad request: worker already exists?")

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
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        filename = os.path.join("/etc/lava-server/dispatcher.d", "%s.yaml" % hostname)
        try:
            with open(filename, "r") as f_in:
                return xmlrpc.client.Binary(f_in.read().encode("utf-8"))
        except OSError:
            raise xmlrpc.client.Fault(
                404, "Worker '%s' does not have a configuration" % hostname
            )

    @check_perm("lava_scheduler_app.change_worker")
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
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        filename = os.path.join("/etc/lava-server/dispatcher.d", "%s.yaml" % hostname)
        try:
            with open(filename, "w") as f_out:
                f_out.write(config)
                return True
        except OSError:
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
        workers = Worker.objects.all().order_by("hostname")
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
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        return {
            "hostname": worker.hostname,
            "description": worker.description,
            "state": worker.get_state_display(),
            "health": worker.get_health_display(),
            "devices": [
                d.hostname for d in worker.device_set.all().order_by("hostname")
            ],
            "last_ping": worker.last_ping,
        }

    @check_perm("lava_scheduler_app.change_worker")
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
                raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

            if description is not None:
                worker.description = description

            if health is not None:
                if health == "ACTIVE":
                    worker.go_health_active(self.user, "xmlrpc api")
                elif health == "MAINTENANCE":
                    worker.go_health_maintenance(self.user, "xmlrpc api")
                elif health == "RETIRED":
                    worker.go_health_retired(self.user, "xmlrpc api")
                else:
                    raise xmlrpc.client.Fault(400, "Invalid health: %s" % health)

            worker.save()
