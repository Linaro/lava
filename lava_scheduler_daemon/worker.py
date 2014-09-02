# Copyright (C) 2014 Linaro Limited
#
# Author: Senthil Kumaran <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Scheduler.
#
# LAVA Scheduler is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3 as
# published by the Free Software Foundation
#
# LAVA Scheduler is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Scheduler.  If not, see <http://www.gnu.org/licenses/>.

import time
import logging
import platform
import urlparse
import xmlrpclib
import simplejson
import lava_dispatcher.config as dispatcher_config

from urllib2 import URLError

from linaro_django_xmlrpc.models import AuthToken

from lava_tool.authtoken import AuthenticatingServerProxy, MemoryAuthBackend
from lava.tool.errors import CommandError

from lava_scheduler_app import utils
from lava_scheduler_app.models import (
    User,
    Worker)


def _get_scheduler_rpc():
    """Returns the scheduler xmlrpc AuthicatingServerProxy object.
    """
    username = 'lava-health'  # We assume this user exists always.
    user = User.objects.get(username=username)
    rpc2_url = Worker.get_rpc2_url()

    try:
        token = AuthToken.objects.filter(user=user)[0]
    except IndexError:
        token = AuthToken.objects.create(user=user)
        token.save()

    parsed_server = urlparse.urlparse(rpc2_url)
    server = '{0}://{1}:{2}@{3}'.format(parsed_server.scheme, username,
                                        token.secret, parsed_server.hostname)
    if parsed_server.port:
        server += ':' + str(parsed_server.port)
    server += parsed_server.path

    auth_backend = MemoryAuthBackend([(username, rpc2_url, token.secret)])
    server = AuthenticatingServerProxy(server, auth_backend=auth_backend)
    server = server.scheduler

    return server


class WorkerData:

    def __init__(self):
        self.logger = logging.getLogger(__name__ + '.Worker')
        self.worker = {}

    def populate_minimal_worker_data(self):
        """This method populates the minimal information about the worker
        node.
        """
        self.worker['info_size'] = 'minimal'
        self.worker['hostname'] = utils.get_fqdn()
        self.worker['uptime'] = utils.get_uptime()
        self.worker['devices'] = [x.hostname for x in
                                  dispatcher_config.get_devices()]
        self.logger.debug("Minimal worker data populated ...")

    def populate_complete_worker_data(self):
        """This method populates the complete information about the worker
        node, which is a lengthy operation.
        """
        self.populate_minimal_worker_data()
        self.worker['info_size'] = 'complete'
        self.worker['arch'] = platform.machine()
        self.worker['platform'] = platform.platform()
        self.worker['ipaddr'] = utils.get_ip_address()
        self.worker['hardware_info'] = utils.get_lshw_out()
        self.worker['software_info'] = utils.get_software_info()
        self.logger.debug("Complete worker data populated ...")

    def get_worker_data(self):
        """Returns worker related information in json format.
        """
        return self.worker

    def put_heartbeat_data(self, restart=False):
        """Puts heartbeat data via the xmlrpc api.

        If the scheduler daemon was restarted identified by RESTART, populate
        the complete worker data, else populate minimal worker data, if it is
        too long since the last heartbeat data was updated.
        """
        try:
            localhost = Worker.localhost()
            if restart:
                self.populate_complete_worker_data()
            elif localhost.too_long_since_last_heartbeat():
                self.populate_minimal_worker_data()
            else:
                return
        except ValueError:
            self.logger.debug("Worker %s unavailable", utils.get_fqdn())
            self.populate_complete_worker_data()

        MAX_RETRIES = 3
        data = simplejson.dumps(self.worker)

        for retry in range(MAX_RETRIES):
            try:
                server = _get_scheduler_rpc()
                server.worker_heartbeat(data)
                self.logger.debug("Heartbeat updated")
                return
            except (CommandError, URLError, IOError) as err:
                self.logger.debug("Error message: %s", str(err))
            except xmlrpclib.Fault as err:
                time.sleep(1)
                self.logger.debug("Retrying heartbeat update (%d) ...", retry)
            except xmlrpclib.ProtocolError as err:
                self.logger.error("Protocol error occured")
                self.logger.error("URL: %s", err.url)
                self.logger.error("HTTP/HTTPS headers: %s", err.headers)
                self.logger.error("Error code: %d", err.errcode)
                self.logger.error("Error message: %s", err.errmsg)
                raise err
        self.logger.error("Unable to update the Heartbeat, trying later")

    def notify_on_incomplete(self, job_id):
        """
        Worker nodes do not require a working email configuration, so to
        avoid losing email, ask the master via XMLRPC to send out the
        notification emails, if any.
        :param job_id: the TestJob.id which ended in state Incomplete
        """
        if not job_id:
            return
        server = _get_scheduler_rpc()
        server.notify_incomplete_job(job_id)

    def record_master_scheduler_tick(self):
        """Records the master's last scheduler tick timestamp.
        """
        try:
            worker = Worker.localhost()
            if worker.on_master():
                worker.record_last_master_scheduler_tick()
        except Exception as err:
            self.logger.error("Unable to record last master scheduler tick.")
            self.logger.error("Details: %s", err)
