# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db.utils import InterfaceError, OperationalError

from lava_results_app.dbutils import append_failure_comment
from lava_scheduler_app.models import TestJob


def test_append_failure_comment_survives_db_error(mocker, caplog):
    """A database error while storing the comment must not propagate.

    It would fail the whole log request and lava-run would resend
    lines that were already stored.
    """
    job = TestJob(description="test job")
    mocker.patch.object(
        TestJob, "save", side_effect=OperationalError("connection lost")
    )
    append_failure_comment(job, "something broke")
    assert "something broke" in job.failure_comment
    assert "Unable to store failure comment" in caplog.text


def test_append_failure_comment_survives_interface_error(mocker, caplog):
    """A dead connection must not propagate either.

    InterfaceError is not a subclass of DatabaseError, so it needs to be
    caught explicitly.
    """
    job = TestJob(description="test job")
    mocker.patch.object(
        TestJob, "save", side_effect=InterfaceError("connection closed")
    )
    append_failure_comment(job, "something broke")
    assert "something broke" in job.failure_comment
    assert "Unable to store failure comment" in caplog.text
