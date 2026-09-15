# Copyright (C) 2026 Linaro Limited
#
# Author: Ben Copeland <ben.copeland@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import pytest
from django.contrib.auth.models import User
from django.db import transaction

from lava_scheduler_app.models import TestJob


@pytest.mark.django_db
def test_testjob_notifications_after_commit(mocker, django_capture_on_commit_callbacks):
    job = TestJob.objects.create(
        submitter=User.objects.create(username="submitter"), definition="{}"
    )
    job_id = job.id
    dispatch = mocker.patch("lava_scheduler_app.signals.async_send_notifications.delay")

    with django_capture_on_commit_callbacks() as callbacks:
        with transaction.atomic():
            job = TestJob.objects.select_for_update().get(pk=job_id)
            job.state = TestJob.STATE_FINISHED
            job.health = TestJob.HEALTH_COMPLETE
            job.save(update_fields=["state", "health"])
            dispatch.assert_not_called()

        job.state = TestJob.STATE_SUBMITTED
        job.health = TestJob.HEALTH_UNKNOWN
        job._old_health = TestJob.HEALTH_COMPLETE

    assert len(callbacks) == 1
    callbacks[0]()

    dispatch.assert_called_once_with(
        job_id, TestJob.STATE_FINISHED, TestJob.HEALTH_COMPLETE, TestJob.HEALTH_UNKNOWN
    )
