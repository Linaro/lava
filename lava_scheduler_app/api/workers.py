# Copyright (C) 2017-2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import pathlib
import xmlrpc.client

from django.db import IntegrityError, transaction

from lava_scheduler_app.api import check_perm
from lava_scheduler_app.models import Worker
from lava_server.files import File
from linaro_django_xmlrpc.models import ExposedV2API


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
        The server will first try
        /etc/lava-server/dispatcher.d/<hostname>/dispatcher.yaml and fallback to
        /etc/lava-server/dispatcher.d/<hostname>.yaml

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker

        Return value
        ------------
        This function returns the worker configuration
        """
        # Sanitize hostname as we will use it in a path
        if len(pathlib.Path(hostname).parts) != 1:
            raise xmlrpc.client.Fault(400, "Invalid worker name")

        # Find the worker in the database
        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        try:
            return xmlrpc.client.Binary(
                File("dispatcher", hostname).read().encode("utf-8")
            )
        except FileNotFoundError:
            raise xmlrpc.client.Fault(
                404, "Worker '%s' does not have a dispatcher configuration" % hostname
            )
        except OSError as exc:
            raise xmlrpc.client.Fault(
                400, "Unable to read dispatcher configuration: %s" % exc.strerror
            )

    def get_env(self, hostname):
        """
        Name
        ----
        `scheduler.workers.get_env` (`hostname`)

        Description
        -----------
        Return the worker environment
        The server will first try
        /etc/lava-server/dispatcher.d/<hostname>/env.yaml and fallback to
        /etc/lava-server/env.yaml

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker

        Return value
        ------------
        This function returns the worker environment
        """
        # Sanitize hostname as we will use it in a path
        if len(pathlib.Path(hostname).parts) != 1:
            raise xmlrpc.client.Fault(400, "Invalid worker name")

        # Find the worker in the database
        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        try:
            return xmlrpc.client.Binary(File("env", hostname).read().encode("utf-8"))
        except FileNotFoundError:
            raise xmlrpc.client.Fault(
                404, "Worker '%s' does not have an env file" % hostname
            )
        except OSError as exc:
            raise xmlrpc.client.Fault(400, "Unable to read env file: %s" % exc.strerror)

    def get_env_dut(self, hostname):
        """
        Name
        ----
        `scheduler.workers.get_env_dut` (`hostname`)

        Description
        -----------
        Return the worker DUT environment
        The server will first try
        /etc/lava-server/dispatcher.d/<hostname>/env-dut.yaml and fallback to
        /etc/lava-server/env-dut.yaml

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker

        Return value
        ------------
        This function returns the worker environment
        """
        # Sanitize hostname as we will use it in a path
        if len(pathlib.Path(hostname).parts) != 1:
            raise xmlrpc.client.Fault(400, "Invalid worker name")

        # Find the worker in the database
        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        try:
            return xmlrpc.client.Binary(
                File("env-dut", hostname).read().encode("utf-8")
            )
        except FileNotFoundError:
            raise xmlrpc.client.Fault(
                404, "Worker '%s' does not have an env-dut file" % hostname
            )
        except OSError as exc:
            raise xmlrpc.client.Fault(
                400, "Unable to read env-dut file: %s" % exc.strerror
            )

    @check_perm("lava_scheduler_app.change_worker")
    def set_config(self, hostname, config):
        """
        Name
        ----
        `scheduler.workers.set_config` (`hostname`, `config`)

        Description
        -----------
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
        # Sanitize hostname as we will use it in a path
        if len(pathlib.Path(hostname).parts) != 1:
            raise xmlrpc.client.Fault(400, "Invalid worker name")

        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        with contextlib.suppress(OSError):
            File("dispatcher", hostname).write(config)
            return True

        return False

    @check_perm("lava_scheduler_app.change_worker")
    def set_env(self, hostname, env):
        """
        Name
        ----
        `scheduler.workers.set_env` (`hostname`, `env`)

        Description
        -----------
        Set the worker environment

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker
        `env`: string
          The worker environment as a yaml file

        Return value
        ------------
        True if the environment was saved to file, False otherwise.
        """
        # Sanitize hostname as we will use it in a path
        if len(pathlib.Path(hostname).parts) != 1:
            raise xmlrpc.client.Fault(400, "Invalid worker name")

        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        with contextlib.suppress(OSError):
            File("env", hostname).write(env)
            return True

        return False

    @check_perm("lava_scheduler_app.change_worker")
    def set_env_dut(self, hostname, env):
        """
        Name
        ----
        `scheduler.workers.set_env_dut` (`hostname`, `env`)

        Description
        -----------
        Set the worker environment for DUT

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker
        `env`: string
          The worker environment as a yaml file

        Return value
        ------------
        True if the environment was saved to file, False otherwise.
        """
        # Sanitize hostname as we will use it in a path
        if len(pathlib.Path(hostname).parts) != 1:
            raise xmlrpc.client.Fault(400, "Invalid worker name")

        try:
            Worker.objects.get(hostname=hostname)
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)

        with contextlib.suppress(OSError):
            File("env-dut", hostname).write(env)
            return True

        return False

    def list(self, show_all=False):
        """
        Name
        ----
        `scheduler.workers.list` (`show_all=False`)

        Description
        -----------
        List workers

        Arguments
        ---------
        `show_all`: boolean
          Show all workers, including retired

        Return value
        ------------
        This function returns an XML-RPC array of workers
        """
        workers = Worker.objects.all()
        if not show_all:
            workers = workers.exclude(health=Worker.HEALTH_RETIRED)
        workers = workers.order_by("hostname")
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

        data = {
            "hostname": worker.hostname,
            "description": worker.description,
            "state": worker.get_state_display(),
            "health": worker.get_health_display(),
            "devices": [
                d.hostname for d in worker.device_set.all().order_by("hostname")
            ],
            "last_ping": worker.last_ping,
            "job_limit": worker.job_limit,
            "version": worker.version,
            "default_config": not File("dispatcher", hostname).is_first(),
            "default_env": not File("env", hostname).is_first(),
            "default_env_dut": not File("env-dut", hostname).is_first(),
        }
        if self.user.is_superuser:
            data["token"] = worker.token
        return data

    @check_perm("lava_scheduler_app.change_worker")
    def update(self, hostname, description=None, health=None, job_limit=None):
        """
        Name
        ----
        `scheduler.workers.update` (`hostname`, `description=None`, `health=None`, `job_limit=None`)

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
        `job_limit`: positive integer
          Set job limit for this worker

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

            if job_limit is not None:
                if not isinstance(job_limit, int) or job_limit < 0:
                    raise xmlrpc.client.fault(400, "Invalid job limit")
                worker.job_limit = job_limit

            worker.save()

    @check_perm("lava_scheduler_app.delete_worker")
    def delete(self, hostname):
        """
        Name
        ----
        `scheduler.workers.delete` (`hostname`)

        Description
        -----------
        Remove a worker.

        Arguments
        ---------
        `hostname`: string
          Hostname of the worker

        Return value
        ------------
        None
        """
        try:
            Worker.objects.get(hostname=hostname).delete()
        except Worker.DoesNotExist:
            raise xmlrpc.client.Fault(404, "Worker '%s' was not found." % hostname)
