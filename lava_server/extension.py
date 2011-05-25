# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
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


from abc import ABCMeta, abstractmethod, abstractproperty
import logging
import pkg_resources


class ILavaServerExtension(object):
    """
    Interface for LAVA Server extensions.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def contribute_to_settings(self, settings):
        """
        Add elements required to initialize this extension into the project
        settings module.
        """

    @abstractmethod
    def contribute_to_urlpatterns(self, urlpatterns):
        """
        Add application specific URLs to root URL patterns of lava-server
        """

    @abstractproperty
    def name(self):
        """
        Name of this extension.
        """

    @abstractproperty
    def version(self):
        """
        Version of this extension.
        """

    @abstractmethod
    def get_main_url(self):
        """
        Absolute URL of the main view
        """


class LavaServerExtension(ILavaServerExtension):
    """
    LAVA Server extension class.

    Implements basic behavior for LAVA server extensions
    """

    # TODO: Publish API objects for xml-rpc

    def __init__(self, slug):
        self.slug = slug

    @abstractproperty
    def app_name(self):
        """
        Name of this extension's primary django application.
        """

    @abstractproperty
    def main_view_name(self):
        """
        Name of the main view
        """

    def contribute_to_settings(self, settings):
        settings['INSTALLED_APPS'].append(self.app_name)
        settings['PREPEND_LABEL_APPS'].append(self.app_name)

    def contribute_to_urlpatterns(self, urlpatterns):
        from django.conf.urls.defaults import url, include 
        urlpatterns += [
            url(r'^{slug}/'.format(slug=self.slug),
                include('{app_name}.urls'.format(app_name=self.app_name)))]

    def get_main_url(self):
        from django.core.urlresolvers import reverse
        return reverse(self.main_view_name)



class ExtensionLoadError(Exception):
    """
    Exception internally raised by extension loader
    """

    def __init__(self, extension, message):
        self.extension = extension
        self.message = message

    def __repr__(self):
        return "ExtensionLoadError(extension={0!r}, message={1!r})".format(
            self.extension, self.message)


class ExtensionLoader(object):
    """
    Helper to load extensions
    """

    def __init__(self):
        self._extensions = None  # Load this lazily so that others can import this module

    @property
    def extensions(self):
        """
        List of extensions
        """
        if self._extensions is None:
            self._extensions = []
            for name in self._find_extensions():
                try:
                    extension = self._load_extension(name)
                except ExtensionLoadError as ex:
                    logging.exception("Unable to load extension %r: %s", name, ex.message)
                else:
                    self._extensions.append(extension)
        return self._extensions

    def contribute_to_settings(self, settings):
        """
        Contribute to lava-server settings module.

        The settings argument is a magic dictionary returned by locals()
        """
        for extension in self.extensions:
            extension.contribute_to_settings(settings)

    def contribute_to_urlpatterns(self, urlpatterns):
        """
        Contribute to lava-server URL patterns
        """
        for extension in self.extensions:
            extension.contribute_to_urlpatterns(urlpatterns)

    def _find_extensions(self):
        return sorted(
            pkg_resources.iter_entry_points(
                'lava_server.extensions'),
            key=lambda ep:ep.name)

    def _load_extension(self, entrypoint):
        """
        Load extension specified by the given name.
        Name must be a string like "module:class". Module may be a
        package with dotted syntax to address specific module.

        @return Imported extension instance, subclass of ILavaServerExtension
        @raises ExtensionLoadError
        """
        try:
            extension_cls = entrypoint.load()
        except ImportError as ex:
            logging.exception("Unable to load extension entry point: %r", entrypoint)
            raise ExtensionLoadError(
                entrypoint,
                "Unable to load extension entry point")
        if not issubclass(extension_cls, ILavaServerExtension):
            raise ExtensionLoadError(
                extension_cls,
                "Class does not implement ILavaServerExtension interface")
        try:
            extension = extension_cls(entrypoint.name)
        except:
            raise ExtensionLoadError(
                extension_cls, "Unable to instantiate class")
        return extension


# Global loader instance
loader = ExtensionLoader()
