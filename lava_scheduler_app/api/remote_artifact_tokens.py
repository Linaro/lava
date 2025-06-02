# Copyright (C) 2025-present Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import xmlrpc.client

from django.db import IntegrityError

from lava_scheduler_app.models import RemoteArtifactsAuth
from linaro_django_xmlrpc.models import ExposedV2API


class SchedulerRemoteArtifactTokensAPI(ExposedV2API):
    def list(self):
        """
        Name
        ----
        `scheduler.remote_artifact_tokens.list` ()

        Description
        -----------
        List available user remote artifact tokens

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array of token dictionaries
        """
        self._authenticate()
        tokens = RemoteArtifactsAuth.objects.filter(user=self.user)
        return [{"name": t.name, "token": t.token} for t in tokens]

    def show(self, name):
        """
        Name
        ----
        `scheduler.remote_artifact_tokens.show` (`name`)

        Description
        -----------
        Show remote artifact token value

        Arguments
        ---------
        `name`: string
          Name of the remote artifact token

        Return value
        ------------
        Remote artifact token string
        """
        self._authenticate()
        try:
            token = RemoteArtifactsAuth.objects.filter(user=self.user).get(name=name)
            return token.token
        except RemoteArtifactsAuth.DoesNotExist:
            raise xmlrpc.client.Fault(404, f"Token '{name}' was not found.")

    def add(self, name, token):
        """
        Name
        ----
        `scheduler.remote_artifact_tokens.add` (`name`, `token`)

        Description
        -----------
        Create a remote artifact token

        Arguments
        ---------
        `name`: string
          Name of the remote artifact token
        `token`: string
          Value of the remote artifact token

        Return value
        ------------
        None
        """
        self._authenticate()
        try:
            RemoteArtifactsAuth.objects.create(user=self.user, name=name, token=token)
        except IntegrityError:
            raise xmlrpc.client.Fault(400, "Bad request: token already exists?")

    def delete(self, name):
        """
        Name
        ----
        `scheduler.remote_artifact_tokens.delete` (`name`)

        Description
        -----------
        Remove a remote artifact token

        Arguments
        ---------
        `name`: string
          Name of the remote artifact token

        Return value
        ------------
        None
        """
        self._authenticate()
        try:
            RemoteArtifactsAuth.objects.get(user=self.user, name=name).delete()
        except RemoteArtifactsAuth.DoesNotExist:
            raise xmlrpc.client.Fault(404, f"Token '{name}' was not found.")
