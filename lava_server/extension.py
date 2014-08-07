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

"""
lava_server.extension
=====================

LAVA Server automatically loads extensions registered under the
``lava_server.extensions`` entry point namespace. Each entry point
must be a subclass of :class:`lava_server.extension.IExtension`
"""


from abc import ABCMeta, abstractmethod, abstractproperty
import logging
import pkg_resources


class IExtension(object):
    """
    Interface for LAVA Server extensions.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, slug):
        """
        Remember slug name
        """

    @abstractmethod
    def contribute_to_settings(self, settings_module):
        """
        Add elements required to initialize this extension into the project
        settings module.
        """

    @abstractmethod
    def contribute_to_settings_ex(self, settings_module, settings_object):
        """
        This method is similar to contribute_to_settings() but allows
        implementation to access a settings object from django-debian. This
        allows extensions to read settings provided by local system
        administrator.
        """

    @abstractmethod
    def contribute_to_urlpatterns(self, urlpatterns, mount_point):
        """
        Add application specific URLs to root URL patterns of lava-server
        """

    @abstractproperty
    def api_class(self):
        """
        Subclass of linaro_django_xmlrpc.models.ExposedAPI for this extension.

        The methods of the class returned from here will be available at /RPC2
        under the name used to register the extension.  Return None if no
        methods should be added.
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

    @abstractproperty
    def front_page_template(self):
        """
        Name of the front page template to {% include %}, may be None
        """

    @abstractmethod
    def get_front_page_context(self):
        """
        Context available to the front page template
        """

    @abstractmethod
    def get_main_url(self):
        """
        Absolute URL of the main view
        """

    @abstractmethod
    def get_menu(self):
        """
        Return a Menu object
        """


# Old longish name, we know it's LAVA already
ILavaServerExtension = IExtension


class Menu(object):
    """
    Menu (for navigation)
    """

    def __init__(self, label, url, sub_menu=None):
        self.label = label
        self.url = url
        self.sub_menu = sub_menu or []


class HeadlessExtension(ILavaServerExtension):
    """
    Base class for building headless extensions.

    The only required things to implement are two ``@property`` functions. You
    will need to implement :attr:`~ILavaServerExtension.name` and
    :attr:`~ILavaServerExtension.version`.

    Meaningful extensions will want to implement
    :meth:`~ILavaServerExtension.contribute_to_settings_ex` and add additional
    applications to ``INSTALLED_APPS``
    """

    def __init__(self, slug):
        self.slug = slug

    def contribute_to_settings(self, settings_module):
        pass

    def contribute_to_settings_ex(self, settings_module, settings_object):
        pass

    def contribute_to_urlpatterns(self, urlpatterns, mount_point):
        pass

    @property
    def api_class(self):
        return None

    @property
    def front_page_template(self):
        return None

    def get_front_page_context(self):
        return {}

    def get_main_url(self):
        pass

    def get_menu(self):
        pass


class DeprecatedExtension(HeadlessExtension):
    """
    If an extension ever contributed to schema changes in the DB, then we
    can't just delete it alltogher without causing problems with our
    south migrations. This is a simple class to keep the extension somewhat
    invisible to the UI, but visible to Django for the DB needs.
    """
    @abstractproperty
    def app_name(self):
        """
        Name of this extension's primary django application.
        (needed for south migrations)
        """

    def contribute_to_settings(self, settings_module):
        settings_module['INSTALLED_APPS'].append(self.app_name)
        settings_module['STATICFILES_PREPEND_LABEL_APPS'].append(self.app_name)

    @property
    def version(self):
        return "deprecated"


class Extension(ILavaServerExtension):
    """
    Base class for commmon extensions.

    This class implements most of the :class:`IExtension` interface leaving a
    only handful of more concrete methods and properties to be implemented.
    """

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

    def get_menu(self):
        from django.core.urlresolvers import reverse
        return Menu(self.name, reverse(self.main_view_name))

    @property
    def front_page_template(self):
        return None

    def get_front_page_context(self):
        return {}

    @property
    def api_class(self):
        """
        Subclass of linaro_django_xmlrpc.models.ExposedAPI for this extension.

        Return None by default for no API.
        """
        return None

    def contribute_to_settings(self, settings_module):
        settings_module['INSTALLED_APPS'].append(self.app_name)
        settings_module['STATICFILES_PREPEND_LABEL_APPS'].append(self.app_name)

    def contribute_to_settings_ex(self, settings_module, settings_object):
        pass

    def contribute_to_urlpatterns(self, urlpatterns, mount_point):
        from django.conf.urls import url, include
        urlpatterns += [
            url(r'^{mount_point}{slug}/'.format(mount_point=mount_point, slug=self.slug),
                include('{app_name}.urls'.format(app_name=self.app_name)))]

    def get_main_url(self):
        from django.core.urlresolvers import reverse
        return reverse(self.main_view_name)


LavaServerExtension = Extension


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
        # Load this lazily so that others can import this module
        self._extensions = None
        self._mapper = None

    @property
    def xmlrpc_mapper(self):
        if self._mapper is None:
            from lava_server.xmlrpc import LavaMapper
            mapper = LavaMapper()
            mapper.register_introspection_methods()
            for extension in self.extensions:
                api_class = extension.api_class
                if api_class is not None:
                    mapper.register(api_class, extension.slug)
            self._mapper = mapper
        return self._mapper

    @property
    def extensions(self):
        """
        List of extensions
        """

        class ExtensionMapping(object):
            """
            Class that exposes extensions by application name
            """

            def __init__(self, extension_list):
                self._extension_list = extension_list

            def __getattr__(self, attr):
                for extension in self._extension_list:
                    if extension.app_name == attr:
                        return extension

        class ExtensionList(list):
            """
            List with an additional property, useful for Django views
            """

            @property
            def as_mapping(self):
                return ExtensionMapping(self)

        if self._extensions is None:
            self._extensions = ExtensionList()
            for name in self._find_extensions():
                try:
                    extension = self._load_extension(name)
                except ExtensionLoadError as ex:
                    logging.exception(
                        "Unable to load extension %r: %s", name, ex.message)
                else:
                    self._extensions.append(extension)
        return self._extensions

    def contribute_to_settings(self, settings_module, settings_object=None):
        """
        Contribute to lava-server settings module.

        The settings_object is optional (it may be None) and allows extensions
        to look at the django-debian settings object. The settings_module
        argument is a magic dictionary returned by locals()
        """
        for extension in self.extensions:
            extension.contribute_to_settings(settings_module)
            if settings_object is not None:
                extension.contribute_to_settings_ex(
                    settings_module, settings_object)

    def contribute_to_urlpatterns(self, urlpatterns, mount_point):
        """
        Contribute to lava-server URL patterns
        """
        for extension in self.extensions:
            extension.contribute_to_urlpatterns(urlpatterns, mount_point)

    def _find_extensions(self):
        return sorted(
            pkg_resources.iter_entry_points(
                'lava_server.extensions'),
            key=lambda ep: ep.name)

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
        except ImportError:
            logging.exception(
                "Unable to load extension entry point: %r", entrypoint)
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
