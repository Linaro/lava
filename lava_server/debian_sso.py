# Copyright 2013 The Distro Tracker Developers
# See the COPYRIGHT file at http://deb.li/DTAuthors
#
# Adapted to work directly with the django user model
# instead of DistroTracker UserEmail
# 2016 Neil Williams <neil.williams@linaro.org>
#
# This file is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import ldap
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.contrib.auth.backends import RemoteUserBackend
from django.contrib import auth
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured


class DebianSsoUserMiddleware(RemoteUserMiddleware):
    """
    Middleware that initiates user authentication based on the REMOTE_USER
    field provided by Debian's SSO system, or based on the SSL_CLIENT_S_DN_CN
    field provided by the validation of the SSL client certificate generated
    by sso.debian.org.

    If the currently logged in user is a DD (as identified by having a
    @debian.org address), he is forcefully logged out if the header is no longer
    found or is invalid.

    To enable, set "AUTH_DEBIAN_SSO" = true in /etc/lava-server/settings.conf
    (JSON syntax). There is no deduplication of users in lava-server, it is
    NOT supported to have Debian SSO and LDAP configured on the same instance.

    """
    dacs_header = 'REMOTE_USER'
    cert_header = 'SSL_CLIENT_S_DN_CN'

    @staticmethod
    def dacs_user_to_email(username):
        parts = [part for part in username.split(':') if part]
        federation, jurisdiction = parts[:2]
        if (federation, jurisdiction) != ('DEBIANORG', 'DEBIAN'):
            return
        username = parts[-1]
        if '@' in username:
            return username  # Full email already
        return username + '@debian.org'

    @staticmethod
    def is_debian_member(user):
        return user.email.endswith('@debian.org')

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the DebianSsoUserMiddleware class.")

        dacs_user = request.META.get(self.dacs_header)
        cert_user = request.META.get(self.cert_header)
        if cert_user is not None:
            remote_user = cert_user
        elif dacs_user is not None:
            remote_user = self.dacs_user_to_email(dacs_user)
        else:
            # Debian developers can only authenticate via SSO/SSL certs
            # so log them out now if they no longer have the proper META
            # variable
            if request.user.is_authenticated():
                if self.is_debian_member(request.user):
                    auth.logout(request)
            return

        if request.user.is_authenticated():
            user = User.objects.filter(email=request.user.email)
            if user.exists():
                # The currently logged in user matches the one given by the
                # headers.
                return

        # This will create the user if it doesn't exist
        user = auth.authenticate(remote_user=remote_user)
        if user:
            # User is valid. Set request.user and persist user in the session
            # by logging the user in.
            request.user = user
            auth.login(request, user)


class DebianSsoUserBackend(RemoteUserBackend):
    """
    The authentication backend which authenticates the provided remote user
    (identified by his @debian.org email) in Django. If a matching User
    model instance does not exist, one is automatically created. In that case
    the DDs first and last name are pulled from Debian's LDAP.
    """

    def generate_unique_username(self, count, slug):  # pylint: disable=no-self-use
        username = '%s%d' % (slug, count)
        try:
            User.objects.get(username=username)
            count += 1
            return generate_unique_username(count)
        except User.DoesNotExist:
            return username

    def ensure_unique_username(self, username):  # pylint: disable=no-self-use
        count = 0
        try:
            User.objects.get(username=username)
            return self.generate_unique_username(count, username)
        except User.DoesNotExist:
            return username

    def authenticate(self, remote_user):
        if not remote_user:
            return

        user = User.objects.filter(email=remote_user)
        if user:
            return user[0]
        kwargs = {}
        names = self.get_user_details(remote_user)
        if names:
            kwargs.update(names)
        username = "sso-user"
        email_list = remote_user.split('@')
        if len(email_list) > 1:
            username = email_list[0]
        username = self.ensure_unique_username(username)
        user = User.objects.create_user(username=username, email=remote_user, **kwargs)
        return user

    @staticmethod
    def get_uid(remote_user):
        # Strips off the @debian.org part of the email leaving the uid
        if remote_user.endswith('@debian.org'):
            return remote_user[:-11]
        return remote_user

    def get_user_details(self, remote_user):
        """
        Gets the details of the given user from the Debian LDAP.
        :return: Dict with the keys ``first_name``, ``last_name``
            ``None`` if the LDAP lookup did not return anything.
        """
        if ldap is None:
            return None
        if not remote_user.endswith('@debian.org'):
            # We only know how to extract data for DD via LDAP
            return None

        service = ldap.initialize('ldap://db.debian.org')
        result_set = service.search_s(
            'dc=debian,dc=org',
            ldap.SCOPE_SUBTREE,  # pylint: disable=no-member
            'uid={}'.format(self.get_uid(remote_user)),
            None)
        if not result_set:
            return None

        result = result_set[0]
        return {
            'first_name': result[1]['cn'][0].decode('utf-8'),
            'last_name': result[1]['sn'][0].decode('utf-8'),
        }
