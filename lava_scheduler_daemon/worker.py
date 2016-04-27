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

import logging
import urlparse

from linaro_django_xmlrpc.models import AuthToken
from lava_tool.authtoken import AuthenticatingServerProxy, MemoryAuthBackend
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

    def get_worker_data(self):
        """Returns worker related information in json format.
        """
        return self.worker

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
