# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db.utils import InterfaceError

from lava_scheduler_app.models import TestJob


def test_set_failure_comment_survives_interface_error(mocker, caplog):
    """A dead connection while storing the comment must not propagate.

    InterfaceError is not a subclass of DatabaseError, so it needs to be
    caught explicitly.
    """
    job = TestJob(description="test job")
    mocker.patch.object(TestJob, "save", side_effect=InterfaceError("connection closed"))
    job.set_failure_comment("something broke")
    assert "something broke" in job.failure_comment
    assert "Unable to store failure comment" in caplog.text
