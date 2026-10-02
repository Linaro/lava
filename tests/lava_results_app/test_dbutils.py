# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db.utils import InterfaceError, OperationalError

from lava_results_app.dbutils import (
    FAILURE_COMMENT_MAX_LENGTH,
    append_failure_comment,
)
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

    InterfaceError is caught explicitly (it is not a DatabaseError
    subclass, and the explicit name keeps the dead-connection case
    visible).
    """
    job = TestJob(description="test job")
    mocker.patch.object(
        TestJob, "save", side_effect=InterfaceError("connection closed")
    )
    append_failure_comment(job, "something broke")
    assert "something broke" in job.failure_comment
    assert "Unable to store failure comment" in caplog.text


def test_append_failure_comment_caps_growth(mocker):
    """The comment stops growing once it is long enough.

    Each rejected result calls this, so a bad batch would keep
    growing the field and saving the job forever.
    """
    job = TestJob(description="test job")
    save = mocker.patch.object(TestJob, "save")
    for _ in range(100):
        append_failure_comment(job, "x" * 256)
    # The cap is on the result of the append, not on the value before it:
    # only the messages that still fit get appended, one save per append.
    assert len(job.failure_comment) <= FAILURE_COMMENT_MAX_LENGTH
    assert save.call_count == FAILURE_COMMENT_MAX_LENGTH // 256
