# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: GPL-2.0-or-later
import pytest
from django.urls import reverse

from lava_common.yaml import yaml_safe_load
from lava_scheduler_app.models import TestJob, User


@pytest.fixture
def user():
    return User.objects.create_user("user")


@pytest.mark.django_db
def test_metadata_export(client, user):
    job = TestJob.objects.create(
        submitter=user, is_public=True, metadata={"build_id": "1234"}
    )

    response = client.get(reverse("lava.results.job.metadata", args=[job.id]))

    assert response.status_code == 200
    assert yaml_safe_load(response.content) == {"build_id": "1234"}


@pytest.mark.django_db
def test_metadata_export_without_metadata(client, user):
    # jobs without any metadata are common, exporting them is not an error
    job = TestJob.objects.create(submitter=user, is_public=True)

    response = client.get(reverse("lava.results.job.metadata", args=[job.id]))

    assert response.status_code == 200
    assert yaml_safe_load(response.content) == {}
