# Copyright (C) 2018 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

from nose.tools import nottest


class LAVAError(Exception):
    """ Base class for all exceptions in LAVA """
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
    error_help = "InfrastructureError: The Infrastructure is not working " \
                 "correctly. Please report this error to LAVA admins."
    error_type = "Infrastructure"


class JobCanceled(LAVAError):
    """ The job was canceled """
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
    An error that is raised when an un-expected error is catched. Only happen
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
    error_help = "ConfigurationError: The LAVA instance is not configured " \
                 "correctly. Please report this error to LAVA admins."
    error_type = "Configuration"


class MultinodeProtocolTimeoutError(LAVAError):
    error_help = "MultinodeProtocolTimeoutError: Multinode wait/sync call " \
                 "has timed out."
    error_type = "MultinodeTimeout"
