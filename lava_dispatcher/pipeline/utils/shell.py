# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

import os
import pexpect
from lava_dispatcher.pipeline.action import InfrastructureError
from lava_dispatcher.pipeline.log import YamlLogger


def which(path, match=os.path.isfile):
    """
    Simple replacement for the `which` command found on
    Debian based systems. Allows ordinary users to query
    the PATH used at runtime.
    """
    paths = os.environ['PATH'].split(':')
    if os.getuid() != 0:
        # avoid sudo - it may ask for a password on developer systems.
        paths.extend(['/usr/local/sbin', '/usr/sbin', '/sbin'])
    for dirname in paths:
        candidate = os.path.join(dirname, path)
        if match(candidate):
            return candidate
    raise InfrastructureError("Cannot find command '%s' in $PATH" % path)


def wait_for_prompt(connection, prompt_pattern, timeout):
    # One of the challenges we face is that kernel log messages can appear
    # half way through a shell prompt.  So, if things are taking a while,
    # we send a newline along to maybe provoke a new prompt.  We wait for
    # half the timeout period and then wait for one tenth of the timeout
    # 6 times (so we wait for 1.1 times the timeout period overall).
    prompt_wait_count = 0
    if timeout == -1:
        timeout = connection.timeout
    partial_timeout = timeout / 2.0
    logger = YamlLogger("root")
    while True:
        try:
            connection.expect(prompt_pattern, timeout=partial_timeout)
        except pexpect.TIMEOUT:
            if prompt_wait_count < 6:
                logger.debug('Sending newline in case of corruption.')
                prompt_wait_count += 1
                partial_timeout = timeout / 10
                connection.sendline('')
                continue
            else:
                raise
        else:
            break
