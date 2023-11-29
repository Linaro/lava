import pytest


@pytest.fixture(autouse=True)
def update_settings(mocker, tmp_path):
    mocker.patch(
        "lava_scheduler_app.models.TestJob.output_dir", str(tmp_path / "job-output")
    )
