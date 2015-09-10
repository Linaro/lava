#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  settings.py
#
#  Copyright (C) 2011-2013 Linaro Limited
#  Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
#  This file is part of the settings distro-integration package.
#  Copyright 2013 Neil Williams <codehelp@debian.org>
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

"""
Simple integration for Django settings.py

 The rationale here is that the refactoring of lava-server to not require
 lava-deployment-tool when packaged, means that the dbconfig-common
 handling is done by distribution-specific packaging scripts which generate the
 /etc/lava-server/instance.conf and this embeds the database access
 methods into that file. default_database.conf is not needed.
 Under lava-deployment-tool, these settings were duplicated in
 /srv/lava/instances/<INSTANCE>/instance.conf and
 /srv/lava/instances/<INSTANCE>/etc/lava-server/default-database.conf
 When packaged, all settings are in /etc/lava-server/instance.conf

 Only the secret key is separate.

 JSON settings remain in settings.conf, when packaged this file
 exists at /etc/lava-server/settings.conf
"""

from lava_server.settings.secret_key import get_secret_key
from lava_server.settings.config_file import ConfigFile
import json
import os


class Settings(object):
    """
    Settings object for better integration with Django and distros

    Example usage (inside your settings.py):

        from lava_server.settings import Settings

        DISTRO_SETTINGS = Settings("yourappname")
        DATABASES = {"default": DISTRO_SETTINGS.default_database}
        SECRET_KEY = DISTRO_SETTINGS.SECRET_KEY
        # Other settings

    A lot of the fields can be re-defined in a JSON configuration file.
    Usually they have good defaults that allows the application to work
    normally out-of-the-box.

    The settings file is constructed with the SETTINGS_TEMPLATE, the filename
    attribute is "settings" the appname attribute depends on the application.
    For example django-hello application the pathname would be:

        ``/etc/django-hello/settings.conf``

    Note: The secret key value CANNOT be redefined using that file
    (it is stored in a separate, application-writable file).
    """

    # Template used to generate pathnames to various files this class uses
    # e.g. /etc/lava-server/settings.conf
    SETTINGS_TEMPLATE = "/etc/{appname}/{filename}.conf"

    def __init__(self, appname, template=None, mount_point=None):
        # FIXME: make this template distro-agnostic
        if template is None:
            template = os.environ.get("DJANGO_DEBIAN_SETTINGS_TEMPLATE", self.SETTINGS_TEMPLATE)
        if mount_point is None:
            mount_point = "{appname}/".format(appname=appname)
        else:
            mount_point = mount_point
        self._settings_template = template
        self._appname = appname
        self._settings = self._load_settings()
        self._mount_point = self._settings.get(
            "MOUNT_POINT", mount_point
        ).encode("UTF-8")  # ensure we're still in binary string mode
        # NOTE: both lines in this order mean that empty mount point stays
        # empty and root mount point gets sanitized to empty as well.
        # Ensure trailing slash is there
        self._mount_point = self._mount_point.rstrip("/") + "/"
        # Strip leading slashes, this is required
        self._mount_point = self._mount_point.lstrip("/")

    def _get_pathname(self, filename):
        """
        Calculate the pathname of the specified configuration file
        """
        return self._settings_template.format(appname=self._appname, filename=filename)

    def _load_settings(self):
        """
        Load and return settings from the "settings" configuration file.

        The file must be be using JSON format, it is simply loaded and used in
        other parts of this API.

        The file roughly represents the same format as would be created by
        serializing the settings.py module. Not all values are exposed though.
        """
        pathname = self._get_pathname("settings")
        if os.path.exists(pathname):
            with open(pathname, "r") as stream:
                return json.load(stream)
        else:
            return {}

    @property
    def mount_point(self):
        """
        Return the URL prefix where the application is mounted.

        This URL always has no leading slash an ALWAYS has a trailing slash
        """
        return self._mount_point

    def get_setting(self, name, default=None):
        """
        Get setting by name
        """
        return self._settings.get(name, default)

    @property
    def DEBUG(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#debug

        Bridge for the settings file DEBUG property.

        By default it produces the value ``False``

        Warning:
            Running production sites in with DEBUG is very dangerous. While in
            DEBUG mode the server will consume more memory with each incoming
            request as the history of all SQL commands is retained.
        """
        default = False
        return self._settings.get("DEBUG", default)

    @property
    def SECRET_KEY(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#secret-key

        The key is obtained from ``secret_key`` configuration file that may be
        overwritten on first use (it will be regenerated when corrupted or
        missing)
        """
        pathname = self._get_pathname("secret_key")
        return get_secret_key(pathname)

    @property
    def default_database(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#databases

        The returned value is suitable for the "default" database. The actual
        values are obtained from the "default_database" configuration file that
        is generated by dbconfig-common as requested by lava_server in one of
        the maintainer scripts

        Expects:
        {'ENGINE': "django.db.backends.postgresql_psycopg2",
        'NAME': $(LAVA_DB_NAME),
        'USER': $(LAVA_DB_USER),
        'PASSWORD': $(LAVA_DB_PASSWORD),
        'HOST': '',
        'PORT': $(LAVA_DB_PORT)

        """
        pathname = self._get_pathname("instance")
        config = ConfigFile.load(pathname)
        pgengine = "django.db.backends.postgresql_psycopg2"  # FIXME
        dbname = config.LAVA_DB_NAME if hasattr(config, 'LAVA_DB_NAME') else ''
        dbuser = config.LAVA_DB_USER if hasattr(config, 'LAVA_DB_USER') else ''
        dbpass = config.LAVA_DB_PASSWORD if hasattr(config, 'LAVA_DB_PASSWORD') else ''
        dbhost = config.LAVA_DB_SERVER if (hasattr(config, 'LAVA_DB_SERVER') and
                                           config.LAVA_DB_SERVER is not "") else '127.0.0.1'
        dbport = config.LAVA_DB_PORT if hasattr(config, 'LAVA_DB_PORT') else ''
        return {
            'ENGINE': pgengine,
            'NAME': dbname,
            'USER': dbuser,
            'PASSWORD': dbpass,
            'HOST': dbhost,
            'PORT': dbport
        }

    @property
    def MEDIA_ROOT(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#media-root

        Bridge for the settings file MEDIA_ROOT property.

        By default it produces the string:

            ``"/var/lib/{appname}/media/"``

        """
        default = "/var/lib/{appname}/media/".format(appname=self._appname)
        return self._settings.get("MEDIA_ROOT", default)

    @property
    def LOG_SIZE_LIMIT(self):
        default = 25
        return self._settings.get("LOG_SIZE_LIMIT", default)

    @property
    def MEDIA_URL(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#media-url

        Bridge for the settings file MEDIA_URL property.

        By default it produces the string:

            ``"/{mount_point}media/"``

        """
        default = "/{mount_point}media/".format(mount_point=self.mount_point)
        return self._settings.get("MEDIA_URL", default)

    @property
    def STATIC_ROOT(self):
        """
        Similar to MEDIA_ROOT but only for static files shipped with each application.

        Bridge for the settings file STATIC_ROOT property.

        By default it produces the string:

            ``"/var/lib/{appname}/static/"``

        """
        default = "/var/lib/{appname}/static/".format(appname=self._appname)
        return self._settings.get("STATIC_ROOT", default)

    @property
    def STATIC_URL(self):
        """
        Similar to MEDIA_URL but only for static files shipped with each application.

        Bridge for the settings file STATIC_URL property.

        By default it produces the string:

            ``"/{mount_point}static/"``
        """
        default = "/{mount_point}static/".format(mount_point=self.mount_point)
        return self._settings.get("STATIC_URL", default)

    @property
    def ADMIN_MEDIA_PREFIX(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#admin-media-prefix

        Bridge for the settings file ADMIN_MEDIA_DIRS property.

        By default it produces the string:
            ``"{STATIC_URL}admin/"``
        """
        default = self.STATIC_URL + "admin/"
        return self._settings.get("ADMIN_MEDIA_PREFIX", default)

    @property
    def TEMPLATE_DIRS(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#template-dirs

        Bridge for the settings file TEMPLATE_DIRS property.

        By default it produces two directories:

            * ``"/etc/{appname}/templates"``
            * ``"/usr/share/{appname}/templates"``

        The first one is provided for administrators that may wish to override
        one or more templates in a local installation for any purpose. The
        second one is to gain access to standard package templates.
        """
        default = (
            "/etc/{appname}/templates/".format(appname=self._appname),
            "/usr/share/{appname}/templates/".format(appname=self._appname))
        return self._settings.get("TEMPLATE_DIRS", default)

    @property
    def STATICFILES_DIRS(self):
        """
        Similar to TEMPLATE_DIRS but only for static files shipped with each application.

        Bridge for the settings file STATICFILES_DIRS property.

        By default it produces one tuple:

            * (appname, ``"/usr/share/{appname}/htdocs/"``)

        """
        default = (
            (self._appname, "/usr/share/{appname}/htdocs/".format(appname=self._appname)),
        )
        return self._settings.get("STATICFILES_DIRS", default)

    @property
    def ADMINS(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#admins

        Bridge for the settings file ADMIN property.

        By default it produces only one value

            ``("{appname} Administrator", "root@localhost')``
        """
        default = (
            ('{appname} Administrator'.format(appname=self._appname), 'root@localhost'),
        )
        return self._settings.get("ADMINS", default)

    @property
    def MANAGERS(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#managers

        Bridge for the settings file MANAGERS property.

        By default it returns whatever ADMINS returns.
        """
        return self._settings.get("MANAGERS", self.ADMINS)

    @property
    def SEND_BROKEN_LINK_EMAILS(self):
        """
        See: http://docs.djangoproject.com/en/1.2/ref/settings/#send-broken-link-emails

        Bridge for the settings file SEND_BROKEN_LINK_EMAILS property.

        By default it returns False
        """
        default = False
        return self._settings.get("SEND_BROKEN_LINK_EMAILS", default)

    @property
    def LOGIN_URL(self):
        """
        TODO: Document
        """
        default = "/{mount_point}accounts/login/".format(mount_point=self.mount_point)
        return self._settings.get("LOGIN_URL", default)

    @property
    def LOGIN_REDIRECT_URL(self):
        """
        TODO: Document
        """
        default = "/{mount_point}".format(mount_point=self.mount_point)
        return self._settings.get("LOGIN_REDIRECT_URL", default)

    @property
    def OPENID_SSO_SERVER_URL(self):
        """
        Allow for local preference for Launchpad to support existing
        groups until OAuth is fully supported. Standard installs
        default to Google OpenID which is available until September 2014.
        To use Google+, set the OpenID server in /etc/lava-server/settings.conf :
        "OPENID_SSO_SERVER_URL": "https://www.google.com/accounts/o8/id"
        """
        default = 'https://login.ubuntu.com/'
        return self._settings.get("OPENID_SSO_SERVER_URL", default)

    @property
    def ARCHIVE_ROOT(self):
        """
        Bridge for the settings file ARCHIVE_ROOT property.

        By default it produces the string:

            ``"/var/lib/{appname}/archive/"``

        """
        default = "/var/lib/{appname}/archive/".format(appname=self._appname)
        return self._settings.get("ARCHIVE_ROOT", default)
