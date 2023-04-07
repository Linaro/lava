from pathlib import Path

import pytest

from lava_dispatcher.job import Job


@pytest.fixture
def job():
    return Job(42, {}, None)


def test_tmp_dir(job):
    assert job.tmp_dir is not None
    tmp_dir = Path(job.tmp_dir)
    assert not tmp_dir.exists()
    assert tmp_dir.name == "42"


def test_tmp_dir_with_prefix(job):
    job.parameters["dispatcher"] = {"prefix": "FOOBAR-"}
    tmp_dir = Path(job.tmp_dir)
    assert tmp_dir.name == "FOOBAR-42"


def test_mkdtemp(job):
    d = job.mkdtemp("my-action")
    assert Path(d).exists()
    assert "my-action" in d


def test_mkdtemp_with_prefix(job):
    job.parameters["dispatcher"] = {"prefix": "FOOBAR-"}
    d = Path(job.mkdtemp("my-action"))
    assert d.parent.name == "FOOBAR-42"


def test_mktemp_with_override(job, tmp_path):
    override = tmp_path / "override"
    first = Path(job.mkdtemp("my-action", override=override))
    second = Path(job.mkdtemp("my-assert", override=override))
    assert first.exists()
    assert second.exists()
    assert first != second
    assert first.parent == second.parent
    assert first.parent.name == str(job.job_id)
