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


from abc import ABCMeta, abstractmethod
import logging


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

    # TODO: Publish API objects for xml-rpc
    # TODO: Publish menu items
    # TODO: Publish URLs (perhaps it's better to do that explicitly rather than
    # asking everyone to shove it into contribute_to_settings()


class ExtensionImportError(Exception):

    def __init__(self, extension, message):
        self.extension = extension
        self.message = message

    def __repr__(self):
        return "ExtensionImportError(extension={0!r}, message={1!r})".format(
            extension, message)


class ExtensionLoader(object):
    """
    Helper to load extensions
    """

    def __init__(self, settings):
        self.settings = settings

    def find_extensions(self):
        # TODO: Implement for real
        yield "demo_app.extension:DemoExtension"

    def load_extensions(self):
        for name in self.find_extensions():
            self.install_extension(name)

    def install_extension(self, name):
        try:
            extension_cls = self.import_extension(name)
            extension = extension_cls()
            extension.contribute_to_settings(self.settings)
        except ExtensionImportError as ex:
            logging.exception("Unable to import extension %r: %s", name, ex.message)
        except Exception:
            logging.exception("Unable to install extension %r", name)

    def import_extension(self, name):
        """
        Import extension specified by the given name.
        Name must be a string like "module:class". Module may be a
        package with dotted syntax to address specific module.

        @return Imported extension class implementing ILavaServerExtension
        @raises ExtensionImportError
        """
        try:
            module_or_package_name, class_name = name.split(":", 1)
        except ValueError:
            raise ExtensionImportError(
                name, "Unable to split extension into module and class")
        try:
            module = __import__(module_or_package_name, fromlist=[''])
        except ImportError as ex:
            raise ExtensionImportError(
                name, "Unable to import required modules")
        try:
            extension_cls = getattr(module, class_name)
        except AttributeError:
            raise ExtensionImportError(
                name, "Unable to access class component")
        if not issubclass(extension_cls, ILavaServerExtension):
            raise ExtensionImportError(
                name, "Class does not implement ILavaServerExtension interface")
        return extension_cls
