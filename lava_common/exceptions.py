# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from lava_common.decorators import nottest


class LAVAError(Exception):
    """Base class for all exceptions in LAVA"""

    error_help = ""
    error_type = ""


class InfrastructureError(LAVAError):
    """
    Exceptions based on an error raised by a component of the
    test which is neither the LAVA dispatcher code nor the
    code being executed on the device under test. This includes
    errors arising from the device (like the arndale SD controller
    issue) and errors arising from the hardware to which the device
    is connected (serial console connection, ethernet switches or
    internet connection beyond the control of the device under test).

    Use LAVABug for errors arising from bugs in LAVA code.
    """

    error_help = (
        "InfrastructureError: The Infrastructure is not working "
        "correctly. Please report this error to LAVA admins."
    )
    error_type = "Infrastructure"


class ConnectionClosedError(InfrastructureError):
    """
    Exception raised when the connection is closed by the remote end
    """

    error_help = "ConnectionClosedError: connection closed"


class JobCanceled(LAVAError):
    """The job was canceled"""

    error_help = "JobCanceled: The job was canceled"
    error_type = "Canceled"


class JobError(LAVAError):
    """
    An Error arising from the information supplied as part of the TestJob
    e.g. HTTP404 on a file to be downloaded as part of the preparation of
    the TestJob or a download which results in a file which tar or gzip
    does not recognise.
    """

    error_help = "JobError: Your job cannot terminate cleanly."
    error_type = "Job"


class LAVABug(LAVAError):
    """
    An error that is raised when an un-expected error is caught. Only happen
    when a bug is encountered.
    """

    error_help = "LAVABug: This is probably a bug in LAVA, please report it."
    error_type = "Bug"


@nottest
class TestError(LAVAError):
    """
    An error in the operation of the test definition, e.g.
    in parsing measurements or commands which fail.
    Always ensure TestError is caught, logged and cleared. It is not fatal.
    """

    error_help = "TestError: A test failed to run, look at the error message."
    error_type = "Test"


class ConfigurationError(LAVAError):
    error_help = (
        "ConfigurationError: The LAVA instance is not configured "
        "correctly. Please report this error to LAVA admins."
    )
    error_type = "Configuration"


class LAVATimeoutError(LAVAError):
    error_help = "LAVATimeoutError: test shell has timed out."
    error_type = "LAVATimeout"


class MultinodeProtocolTimeoutError(LAVAError):
    error_help = (
        "MultinodeProtocolTimeoutError: Multinode wait/sync call has timed out."
    )
    error_type = "MultinodeTimeout"


class LAVAServerError(Exception):
    """Subclass for all exceptions on LAVA server side"""

    error_help = ""
    error_type = ""


class ObjectNotPersisted(LAVAServerError):
    error_help = "ObjectNotPersisted: Object is not persisted."
    error_type = "ObjectNotPersisted"


class PermissionNameError(LAVAServerError):
    error_help = "PermissionNameError: Unexisting permission codename."
    error_type = "Unexisting permission codename."


class RequestBodyTooLargeError(LAVAError):
    error_help = "RequestBodyTooLarge: Request body exceeds server settings param."
    error_type = "RequestBodyTooLarge"
