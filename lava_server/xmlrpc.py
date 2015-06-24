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

import xmlrpclib
from django.http import Http404
from dashboard_app.models import Bundle
from dashboard_app.xmlrpc import errors
from django.core.exceptions import PermissionDenied
from lava_scheduler_app.views import get_restricted_job
from lava_scheduler_app.models import Device, DeviceType, DeviceDictionary
from linaro_django_xmlrpc.models import Mapper, SystemAPI
from django.contrib.auth.models import Group, Permission, User


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

    def user_can_view_jobs(self, job_list, username=None):
        """
        Name
        ----
        user_can_view_jobs (`job_list`)

        Administrators only:
        user_can_view_jobs (`job_list`, `username`)

        Description
        -----------
        Check the access permissions on a list of jobs.
        Admins can specify a username as the second argument to run
        the query on behalf of that user.

        Arguments
        ---------
        job_list: list
            list of job ids to query
        username: string
            username of the user to query (admins only)

        Return value
        ------------
        Returns a dictionary where the key is a string of the job_id from
        the job_list, if it exists in the queried instance. The value is a boolean
        for whether the user can access that job.
        {
          '1234': True,
          '1543': False
        }
        If the job number does not exist, that job will be omitted from the
        returned dictionary.
        This function requires authentication with a username and token.

        Example
        -------
        server.system.user_can_view_jobs([1, 2, 3, 4, 99999, 4000])
        {'1': True, '4000': True, '3': True, '2': True, '4': True}

        # if using the username and token of an admin, a different user can be queried:
        server.system.user_can_view_jobs([1, 2, 3, 4, 99999, 4000], 'firstname.lastname')
        {'1': True, '4000': False, '3': True, '2': True, '4': False}

        """
        self._authenticate()
        if type(job_list) is not list:
            raise xmlrpclib.Fault(
                errors.BAD_REQUEST,
                "job list argument must be a list")
        username = self._switch_user(username)
        retval = {}
        for job_id in job_list:
            try:
                get_restricted_job(username, job_id)
            except Http404:
                continue
            except PermissionDenied:
                retval[str(job_id)] = False
                continue
            retval[str(job_id)] = True
        return retval

    def user_can_view_bundles(self, bundle_list, username=None):
        """
        Name
        ----
        user_can_view_bundles (`bundle_list`)

        Administrators only:
        user_can_view_bundles (`bundle_list`, `username`)

        Description
        -----------
        Check the access permissions on a list of bundles.
        Admins can specify a username as the second argument to run
        the query on behalf of that user.

        Arguments
        ---------
        bundle_list: list
            list of bundle sha1sums to query
        username: string
            username of the user to query (admins only)

        Return value
        ------------
        Returns a dictionary where the key is a sha1sum from the bundle_list
        which exists in the queried instance. The value is a boolean
        for whether the user can access that bundle.
        {
          '1b08b2613066d2c4d3ef00584d15e75188eeb9e4': True,
          'eb59cb31c43dfc322c5c5c1d44ce3e74254b4557': False
        }
        If the bundle does not exist, that bundle will be omitted from the
        returned dictionary.
        This function requires authentication with a username and token.

        Example
        -------
        server.system.user_can_view_bundles(
            ['eb59cb31c43dfc322c5c5c1d44ce3e74254b4557',
            '1b08b2613066d2c4d3ef00584d15e75188eeb9e4'])

        {'eb59cb31c43dfc322c5c5c1d44ce3e74254b4557': True, '1b08b2613066d2c4d3ef00584d15e75188eeb9e4': True}

        # if using the username and token of an admin, a different user can be queried:
        server.system.user_can_view_bundles(
            ['eb59cb31c43dfc322c5c5c1d44ce3e74254b4557',
            '1b08b2613066d2c4d3ef00584d15e75188eeb9e4']
            'firstname.lastname')

        {'eb59cb31c43dfc322c5c5c1d44ce3e74254b4557': True, '1b08b2613066d2c4d3ef00584d15e75188eeb9e4': False}

        """
        self._authenticate()
        if type(bundle_list) is not list:
            raise xmlrpclib.Fault(
                errors.BAD_REQUEST,
                "bundle list argument must be a list")
        username = self._switch_user(username)
        retval = {}
        for content_sha1 in bundle_list:
            try:
                bundle = Bundle.objects.get(content_sha1=content_sha1)  # pylint: disable=no-member
                if not bundle.bundle_stream.is_accessible_by(username):
                    retval[content_sha1] = False
            except Bundle.DoesNotExist:  # pylint: disable=no-member
                continue
            retval[content_sha1] = True
        return retval

    def user_can_view_devices(self, device_list, username=None):
        """
        Name
        ----
        user_can_view_devices (`device_list`)

        Administrators only:
        user_can_view_devices (`device_list`, `username`)

        Description
        -----------
        Check the access permissions on a list of devices.
        Admins can specify a username as the second argument to run
        the query on behalf of that user.

        Arguments
        ---------
        device_list: list
            list of device hostnames to query
        username: string
            username of the user to query (admins only)

        Return value
        ------------
        Returns a nested dictionary where the top level key is the device type, the value is
        a list of dictionaries. The key of the second dictionary is a hostname from the device_list
        which exists in the queried instance. The value is a boolean
        for whether the user can access that device.
        If the device is visible, also includes a boolean denoting whether the specified
        device is a pipeline device which can run jobs designed in the dispatcher refactoring.
        If a pipeline device, also includes a boolean denoting whether the specified pipeline
        device exclusively accepts YAML submissions - JSON submissions are rejected if this
        device is marked as exclusive.
        {
            'mustang': [
                {
                    'mustang01': {
                        'visible': True
                        }
                }
            ],
            'panda': [
                {
                    'panda05': {
                        'visible': True
                        }
                    }
            ]
        }

        If the device type is hidden, that type and the nested dictionary for that type
        will be omitted.
        Retired devices will be omitted.
        If the device does not exist, that device will be omitted from the
        returned dictionary.
        This function requires authentication with a username and token.

        Example
        -------

        server.system.user_can_view_devices(['kvm014', 'kvm02'])
        {'qemu':
            [
                {'kvm014': {
                    'exclusive': False,
                    'visible': True,
                    'is_pipeline': True
                    }
                },
                {'kvm02': {
                    'exclusive': True,
                    'visible': True,
                    'is_pipeline': True}
                }
            ]
        }

        # if using the username and token of an admin, a different user can be queried:
        server.system.user_can_view_devices(
            ['mustang01', 'wandboard07', 'imx53-01', 'cubietruck02', 'black01'],
            'firstname.lastname'
        )

        """
        self._authenticate()
        if type(device_list) is not list:
            raise xmlrpclib.Fault(
                errors.BAD_REQUEST,
                "device list argument must be a list")
        username = self._switch_user(username)
        retval = {}
        for hostname in device_list:
            try:
                device = Device.objects.get(hostname=hostname)
            except Device.DoesNotExist:
                continue
            device_type = device.device_type
            if device_type.owners_only and not device.is_owned_by(username):
                continue
            retval.setdefault(device_type.name, [])
            visible = device.is_visible_to(username)
            if visible:
                retval[device_type.name].append({
                    hostname: {
                        'is_pipeline': device.is_pipeline,
                        'visible': visible,
                        'exclusive': device.is_exclusive
                    }
                })
            else:
                retval[device_type.name].append({
                    hostname: {'visible': visible}
                })
        return retval

    def user_can_submit_to_types(self, type_list, username=None):
        """
        Name
        ----
        user_can_submit_to_types (`type_list`)

        Administrators only:
        user_can_submit_to_types (`type_list`, `username`)

        Description
        -----------
        Check the access permissions on a list of device types.
        Admins can specify a username as the second argument to run
        the query on behalf of that user.

        Arguments
        ---------
        type_list: list
            list of device types to query
        username: string
            username of the user to query (admins only)

        Return value
        ------------
        Returns a dictionary where the key is a string of the device_type from
        the type_list, if it exists in the queried instance. The value is a boolean
        for whether the user can submit to any devices of the specified type.
        {
          'panda': True,
          'mustang': False
        }
        If the device type number does not exist, that type will be omitted from the
        returned dictionary.
        This function requires authentication with a username and token.

        Example
        -------
        server.system.user_can_submit_to_types(
            ['mustang', 'panda', 'qemu', 'kvm', 'cubie2']
        )
        {'cubie2': True, 'mustang': False, 'kvm': True, 'qemu': True, 'panda': True}

        # if using the username and token of an admin, a different user can be queried:
        server.system.user_can_submit_to_types(
            ['mustang', 'panda', 'qemu', 'kvm', 'cubie2'],
            'firstname.lastname'
        )

        """
        self._authenticate()
        if type(type_list) is not list:
            raise xmlrpclib.Fault(
                errors.BAD_REQUEST,
                "type list argument must be a list")
        username = self._switch_user(username)
        if not username.has_perm('lava_scheduler_app.add_testjob'):
            raise xmlrpclib.Fault(
                errors.FORBIDDEN,
                "User '%s' does not have permissiont to submit jobs." % username
            )
        retval = {}
        for type_name in type_list:
            try:
                device_type = DeviceType.objects.get(name=type_name)
            except DeviceType.DoesNotExist:
                continue
            devices = Device.objects.filter(device_type=device_type)
            access = []
            for device in devices:
                access.append(device.can_submit(username))
            retval[device_type.name] = any(access)
        return retval


class LavaMapper(Mapper):

    def register_introspection_methods(self):
        """
        Register LavaSystemAPI as 'system' object.

        LavaSystemAPI adds a 'whoami' system method above what the default
        has.
        """
        self.register(LavaSystemAPI, 'system')
