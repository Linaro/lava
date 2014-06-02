# Copyright (C) 2014 Linaro Limited
#
# Author: Milo Casagrande <milo.casagrande@linaro.org>
#
# This file is part of lava-server.
#
# lava-tool is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# as published by the Free Software Foundation
#
# lava-tool is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with lava-tool.  If not, see <http://www.gnu.org/licenses/>.

"""Helper functions for a template."""


def expand_template(template, config):
    """Updates a template based on the values from the provided config.

    :param template: A template to be updated.
    :param config: A Config instance where values should be taken.
    """

    def update(data):
        """Internal recursive function."""
        data_loop = data
        if isinstance(data, dict):
            keys = data.keys()
        elif isinstance(data, list):
            keys = range(len(data))
        else:
            return
        for key in keys:
            entry = data_loop[key]
            if data_loop[key] in config.keys():
                if config.get(entry):
                    data[key] = config.get(entry)
                else:
                    if isinstance(data, dict):
                        del(data[key])
                    else:
                        data[key] = None
            else:
                update(entry)

        if isinstance(data, list):
            data[:] = [x for x in data if x]

    update(template)
