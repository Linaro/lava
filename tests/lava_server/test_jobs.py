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

from lava_scheduler_app.models import TestJob, TestJobUser, User


@pytest.fixture
def job_output_root(tmp_path):
    return tmp_path / "job-output"


@pytest.fixture(autouse=True)
def per_job_output_dir(mocker, tmp_path):
    """
    Force per-job output directories.

    In this test case TestJob.output_dir resolves to a shared job-output path,
    so removing one job deletes the other's logs too.
    """
    job_output_root = tmp_path / "job-output"

    def _output_dir(self):
        return str(job_output_root / str(self.id))

    # Replace the attribute on the class with a genuine property
    mocker.patch.object(TestJob, "output_dir", new=property(_output_dir))


@pytest.fixture
def job1(job_output_root):
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
def job2(job_output_root):
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
    for _ in range(101):
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


@pytest.mark.django_db
def test_jobs_rm_logs_only(job1, job2):
    call_command("jobs", "rm", "--older-than", "10d", "--logs-only")

    assert TestJob.objects.filter(id=job1.id).exists()
    assert not Path(job1.output_dir).exists()

    assert TestJob.objects.filter(id=job2.id).exists()
    assert not Path(job2.output_dir).exists()


@pytest.mark.django_db
def test_jobs_rm_favorite_preserved(job1, job2):
    user = job1.submitter
    user_metadata = TestJobUser(user=user, test_job=job1, is_favorite=True)
    user_metadata.save()

    call_command("jobs", "rm", "--older-than", "1d")

    assert TestJob.objects.filter(id=job1.id).exists()
    assert Path(job1.output_dir).exists()

    assert not TestJob.objects.filter(id=job2.id).exists()
    assert not Path(job2.output_dir).exists()

    call_command("jobs", "rm", "--older-than", "1d", "--no-skip-favorite")

    assert not TestJob.objects.filter(id=job1.id).exists()
    assert not Path(job1.output_dir).exists()


@pytest.fixture
def jobs_without_metadata():
    user = User.objects.create_user("submitter")
    old_job = TestJob.objects.create(
        submitter=user,
        definition="job_name: old\nmetadata:\n  build_id: 1234\n  branch: main\n",
    )
    no_metadata_job = TestJob.objects.create(
        submitter=user, definition="job_name: no metadata\n"
    )
    broken_job = TestJob.objects.create(submitter=user, definition="{{ not yaml")
    return old_job, no_metadata_job, broken_job


@pytest.mark.django_db
def test_jobs_backfill_metadata(jobs_without_metadata):
    old_job, no_metadata_job, broken_job = jobs_without_metadata

    out = StringIO()
    call_command("jobs", "backfill-metadata", stdout=out, stderr=StringIO())
    assert "3 jobs scanned, 1 updated" in out.getvalue()

    old_job.refresh_from_db()
    assert old_job.metadata == {"build_id": "1234", "branch": "main"}
    no_metadata_job.refresh_from_db()
    assert no_metadata_job.metadata == {}
    broken_job.refresh_from_db()
    assert broken_job.metadata == {}


@pytest.mark.django_db
def test_jobs_backfill_metadata_dry_run(jobs_without_metadata):
    old_job = jobs_without_metadata[0]

    call_command(
        "jobs", "backfill-metadata", "--dry-run", stdout=StringIO(), stderr=StringIO()
    )

    old_job.refresh_from_db()
    assert old_job.metadata == {}


@pytest.mark.django_db
def test_jobs_backfill_metadata_id_range(jobs_without_metadata):
    old_job = jobs_without_metadata[0]

    call_command(
        "jobs",
        "backfill-metadata",
        "--start-id",
        str(old_job.id + 1),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    old_job.refresh_from_db()
    assert old_job.metadata == {}

    call_command(
        "jobs",
        "backfill-metadata",
        "--end-id",
        str(old_job.id),
        stdout=StringIO(),
        stderr=StringIO(),
    )

    old_job.refresh_from_db()
    assert old_job.metadata == {"build_id": "1234", "branch": "main"}
