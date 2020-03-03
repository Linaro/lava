# -*- coding: utf-8 -*-
# Copyright (C) 2018 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
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

import pytest
import lava_dispatcher.job
import lava_dispatcher.utils.filesystem


@pytest.fixture(autouse=True)
def tempdir(monkeypatch, tmpdir):
    monkeypatch.setattr(lava_dispatcher.job, "DISPATCHER_DOWNLOAD_DIR", str(tmpdir))
    monkeypatch.setattr(
        lava_dispatcher.utils.filesystem, "tftpd_dir", lambda: str(tmpdir)
    )
