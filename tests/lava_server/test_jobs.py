# Copyright (C) 2020-present Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.utils import timezone

from lava_scheduler_app.models import TestJob, User


@pytest.fixture
def job1(mocker, tmp_path):
    media_root = tmp_path / "media"
    mocker.patch(
        "django.conf.settings.MEDIA_ROOT",
        str(media_root),
    )

    user1 = User.objects.create_user("user1")
    now = timezone.now()
    job1 = TestJob.objects.create(
        submitter=user1,
        state=TestJob.STATE_FINISHED,
        start_time=(now - timedelta(days=92)),
        end_time=(now - timedelta(days=91)),
    )
    job1.save()
    job1_output_dir = Path(job1.output_dir)
    job1_output_dir.mkdir(parents=True)
    (job1_output_dir / "job.yaml").write_text("job1def")
    (job1_output_dir / "output.yaml").write_text("job1log")

    return job1


@pytest.fixture
def job2(mocker, tmp_path):
    media_root = tmp_path / "media"
    mocker.patch(
        "django.conf.settings.MEDIA_ROOT",
        str(media_root),
    )

    user2 = User.objects.create_user("user2")
    now = timezone.now()
    job2 = TestJob.objects.create(
        submitter=user2,
        state=TestJob.STATE_FINISHED,
        start_time=(now - timedelta(days=12)),
        end_time=(now - timedelta(days=11)),
    )
    job2_output_dir = Path(job2.output_dir)
    job2_output_dir.mkdir(parents=True)
    (job2_output_dir / "job.yaml").write_text("job2def")
    (job2_output_dir / "output.yaml").write_text("job2log")

    return job2


@pytest.mark.django_db
def test_jobs_rm_older_than(job1, job2):
    call_command("jobs", "rm", "--older-than", "90d")

    assert not TestJob.objects.filter(id=job1.id).exists()
    assert not Path(job1.output_dir).exists()
    assert TestJob.objects.filter(id=job2.id).exists()
    assert Path(job2.output_dir).exists()

    call_command("jobs", "rm", "--older-than", "10d")
    assert not TestJob.objects.filter(id=job2.id).exists()
    assert not Path(job2.output_dir).exists()


@pytest.mark.django_db
def test_jobs_rm_by_user(job1, job2):
    call_command("jobs", "rm", "--submitter", "user1")

    assert not TestJob.objects.filter(id=job1.id).exists()
    assert not Path(job1.output_dir).exists()
    assert TestJob.objects.filter(id=job2.id).exists()
    assert Path(job2.output_dir).exists()

    call_command("jobs", "rm", "--submitter", "user2")
    assert not TestJob.objects.filter(id=job2.id).exists()
    assert not Path(job2.output_dir).exists()


@pytest.mark.django_db
def test_jobs_rm_slow(mocker):
    user1 = User.objects.create_user("user1")

    out = StringIO()
    call_command("jobs", "rm", "--submitter", "user1", "--slow", stdout=out)
    assert "sleeping 2s..." not in out.getvalue()

    now = timezone.now()
    for i in range(101):
        TestJob.objects.create(
            submitter=user1,
            state=TestJob.STATE_FINISHED,
            start_time=(now - timedelta(days=1)),
            end_time=now,
        )
    assert TestJob.objects.filter(submitter=user1).count() == 101

    out101 = StringIO()
    mocker.patch("lava_server.management.commands.jobs.time.sleep")
    call_command("jobs", "rm", "--submitter", "user1", "--slow", stdout=out101)
    assert "sleeping 2s..." in out101.getvalue()
