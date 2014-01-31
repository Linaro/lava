# Copyright (C) 2013 Linaro
#
# Author: Milo Casagrande <milo.casagrande@linaro.org>
# This file is part of the Patchmetrics package.
#
# Patchmetrics is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Patchmetrics is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Patchwork; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import base64
import httplib
import urllib
import json
import types


class CrowdException(Exception):
    """Base class for Crowd exceptions."""


class CrowdNotFoundException(CrowdException):
    """An exception for 404 status."""


class CrowdForbiddenException(CrowdException):
    """An exception for 403 status."""


class CrowdUnauthorizedException(CrowdException):
    """ An exception for 401 status."""


class CrowdUser(object):
    """An object that depicts a user from the Crowd system.

    It has the following properties:
    name (str)
    display_name (str)
    teams (list)
    emails (list)
    """

    def __init__(self):
        self._display_name = None
        self._emails = None
        self._teams = None
        self._name = None

    @property
    def emails(self):
        return self._emails

    @emails.setter
    def emails(self, value):
        if isinstance(value, types.StringTypes):
            self._emails = [value]
        else:
            self._emails = list(value)

    @property
    def teams(self):
        return self._teams

    @teams.setter
    def teams(self, value):
        if isinstance(value, types.StringTypes):
            self._teams = [value]
        else:
            self._teams = list(value)

    @property
    def display_name(self):
        return self._display_name

    @display_name.setter
    def display_name(self, value):
        self._display_name = value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @staticmethod
    def _user_from_json(data):
        user = CrowdUser()
        user.display_name = data['display-name']
        user.name = data['name']
        user.emails = data['email']
        return user

    @staticmethod
    def from_json(data):
        """Creates a CrowdUser from JSON data.

        The JSON data has to contain these fields:
        display-name
        name
        email

        :param data: The JSON file to load.
        """
        json_data = json.load(data)
        return CrowdUser._user_from_json(json_data)

    @staticmethod
    def from_json_s(string):
        """Creates a CrowdUser from a JSON string.

        The JSON data has to contain these fields:
        display-name
        name
        email

        :param string: The JSON string.
        :type str
        """
        json_data = json.loads(string)
        return CrowdUser._user_from_json(json_data)


class Crowd(object):
    """A Crowd object used to perform query operations."""

    def __init__(self, usr, pwd, url):
        self._usr = usr
        self._pwd = pwd
        assert url.startswith("https://")
        dummy, dummy, self._host, self._uri = url.split("/", 3)
        if ":" in self._host:
            self._host, self._port = self._host.split(":")
        else:
            self._port = 443

        self._auth = base64.encodestring('{0}:{1}'.format(self._usr,
                                                          self._pwd))
        self._headers = {
            "Authorization": "Basic {0}".format(self._auth),
            "Accept": "application/json"
        }

    def get_user(self, email):
        params = {"username": email}

        resource = "/user?{0}".format(urllib.urlencode(params))
        return CrowdUser.from_json_s(self._get_rest_usermanagement(resource))

    def get_user_by_realname(self, first_name, last_name):
        uri = "/search.json?restriction=firstName%3D{}+AND+lastName%3D{}&entity-type=user"
        uri = uri.format(urllib.quote(first_name.encode("utf8")), urllib.quote(last_name.encode("utf8")))
        data = json.loads(self._get_rest_usermanagement(uri))
        if not data["users"]:
            raise CrowdNotFoundException
        if len(data["users"]) > 1:
            print "More than one matching user - ignored"
            raise CrowdNotFoundException
        name = data["users"][0]["name"]
        # Only username is provided by search, not other properties,
        # so we recursively fetch them.
        return self.get_user(name)

    def get_user_with_groups(self, email):
        """Gets all the groups a user is member of.

        :param email: The user email.
        :return A CrowdUser object.
        """
        # First get the user, if it does not exist, we skip all the operations
        # here.
        user = self.get_user(email)

        params = {"username": email}

        resource = "/user/group/nested?{0}".format(
            urllib.urlencode(params))
        data = json.loads(self._get_rest_usermanagement(resource))

        teams = []
        if data["groups"]:
            teams = [x["name"] for x in data["groups"]]
        user.teams = teams

        return user

    def is_valid_user(self, email):
        """Handy function to check if a user exists or not.

        :param email: The user email.
        :return True or False.
        """
        params = {"username": email}

        resource = "/user?{0}".format(urllib.urlencode(params))
        api_url = "/crowd/rest/usermanagement/1{0}".format(resource)

        valid = True
        try:
            self._get(api_url)
        except CrowdNotFoundException:
            # In case of other exceptions, raise them.
            valid = False

        return valid

    def _get_rest_usermanagement(self, resource):
        api_url = "/{0}{1}".format(self._uri, resource)
        return self._get(api_url)

    def _get(self, api_url):
        """Performs a GET operation on the API URL.

        :param api_url: The URL of the API to use.
        :return The response data.
        :raise CrowdNotFoundException if the response status is 404,
            CrowdForbiddenException if status is 403,
            CrowdUnauthorizedException if status is 401, and CrowdException
            in other cases.
        """
        connection = httplib.HTTPSConnection(self._host, str(self._port))
        connection.request("GET", api_url, headers=self._headers)
        resp = connection.getresponse()

        if resp.status == 200:
            return resp.read()
        elif resp.status == 404:
            raise CrowdNotFoundException("Resource not found")
        elif resp.status == 401:
            raise CrowdUnauthorizedException(
                "Authorization not granted to fulfill the request")
        elif resp.status == 403:
            raise CrowdForbiddenException(
                "Access forbidden to fulfill the request")
        else:
            raise CrowdException(
                "Unknown Crowd status {0}".format(resp.status))
