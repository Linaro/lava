# Copyright (C) 2026 Linaro Limited
#
# Author: Fathi Boudra <fathi.boudra@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db.utils import InterfaceError

from lava_results_app.dbutils import FAILURE_COMMENT_MAX_LENGTH
from lava_scheduler_app.models import TestJob


def test_set_failure_comment_survives_interface_error(mocker, caplog):
    """A dead connection while storing the comment must not propagate.

    InterfaceError is caught explicitly (it is not a DatabaseError
    subclass, and the explicit name keeps the dead-connection case
    visible).
    """
    job = TestJob(description="test job")
    mocker.patch.object(
        TestJob, "save", side_effect=InterfaceError("connection closed")
    )
    job.set_failure_comment("something broke")
    assert "something broke" in job.failure_comment
    assert "Unable to store failure comment" in caplog.text


def test_set_failure_comment_caps_growth(mocker):
    """Repeated calls must not grow the field forever."""
    job = TestJob(description="test job")
    save = mocker.patch.object(TestJob, "save")
    for i in range(100):
        job.set_failure_comment("failure %d %s" % (i, "x" * 100))
    assert len(job.failure_comment) <= FAILURE_COMMENT_MAX_LENGTH
    assert save.call_count < 100


def test_set_failure_comment_caps_the_first_message(mocker):
    """The first message is capped too, not only the following ones.

    Callers interpolate dispatcher-supplied data (an invalid testset name,
    say): an unbounded first write would store the field past its cap and then
    refuse every later comment, because the append paths stop once the field
    is full.
    """
    job = TestJob(description="test job")
    save = mocker.patch.object(TestJob, "save")
    job.set_failure_comment("x" * (4 * FAILURE_COMMENT_MAX_LENGTH))
    assert len(job.failure_comment) == FAILURE_COMMENT_MAX_LENGTH
    assert save.call_count == 1
