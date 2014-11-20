# Copyright (C) 2014 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
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

import logging
from lava_dispatcher.pipeline.actions.test.shell import TestShellAction


class MultinodeTestAction(TestShellAction):

    def __init__(self):
        # FIXME: only a stub, untested.
        super(MultinodeTestAction, self).__init__()
        self.name = "multinode-test"
        self.description = "Executing lava-test-runner"
        self.summary = "Multinode Lava Test Shell"

    def validate(self):
        super(MultinodeTestAction, self).validate()
        if not self.valid:
            self.errors = "Invalid base class TestAction"
            return
        self.patterns.update({
            'multinode': r'<LAVA_MULTI_NODE> <LAVA_(\S+) ([^>]+)>',
        })

    def check_patterns(self, event, test_connection):
        """
        Calls the parent check_patterns and drops out of the keep_running
        loop if the parent returns False, otherwise checks for subclass pattern.
        """
        keep = super(MultinodeTestAction, self).check_patterns(event, test_connection)
        if not keep:
            return False
        yaml_log = logging.getLogger("YAML")
        if event == 'multinode':
            name, params = test_connection.match.groups()
            yaml_log.debug("Received Multi_Node API <LAVA_%s>", name)
            params = params.split()
            try:
                ret = self.signal_director.signal(name, params)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            # FIXME: define the possible exceptions!
            # except:
            #    raise JobError("on_signal(Multi_Node) failed")
            return ret
        return True
