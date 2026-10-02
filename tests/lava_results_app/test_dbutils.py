# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db.utils import OperationalError

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


def test_append_failure_comment_caps_growth(mocker):
    """The comment stops growing once it is long enough.

    Each rejected result calls this, so a bad batch would keep
    growing the field and saving the job forever.
    """
    job = TestJob(description="test job")
    save = mocker.patch.object(TestJob, "save")
    for _ in range(100):
        append_failure_comment(job, "x" * 256)
    assert len(job.failure_comment) < 5000
    assert save.call_count < 20
