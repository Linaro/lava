# Copyright (C) 2020 Linaro Limited
#
# Author: Antonio Terceiro <antonio.terceiro@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from lava_common.download import resolve_download_dir
from lava_common.yaml import yaml_safe_dump, yaml_safe_load

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any


def get_job_dir(job_id: str, download_dir: str | Path | None = None) -> Path:
    """
    Directory holding the files of a job inside the dispatcher download
    directory.

    download_dir is None for the callers running outside of a job, like
    lava-dispatcher-host, which fall back to the default location.
    """
    return resolve_download_dir(download_dir) / str(job_id)


def get_mapping_path(job_id: str, download_dir: str | Path | None = None) -> Path:
    return get_job_dir(job_id, download_dir) / "usbmap.yaml"


def iter_mapping_paths(download_dir: str | Path | None = None) -> Iterator[Path]:
    yield from resolve_download_dir(download_dir).glob("*/usbmap.yaml")


def add_device_container_mapping(
    job_id: str,
    device_info: dict[str, Any],
    container: str,
    container_type: str = "docker",
    device_paths: list[str] | None = None,
    download_dir: str | Path | None = None,
) -> None:
    validate_device_info(device_info)
    item: dict[str, Any] = {
        "device_info": device_info,
        "container": container,
        "container_type": container_type,
        "job_id": job_id,
    }
    if device_paths:
        item["device_paths"] = list(device_paths)
    mapping_path = get_mapping_path(job_id, download_dir)
    data = load_mapping_data(mapping_path)

    # remove old mappings for the same device_info
    newdata = [old for old in data if old["device_info"] != item["device_info"]]
    newdata.append(item)

    mapping_path.parent.mkdir(exist_ok=True)
    with open(mapping_path, "w") as f:
        f.write(yaml_safe_dump(newdata))


def remove_device_container_mappings(
    job_id: str, download_dir: str | Path | None = None
) -> None:
    get_mapping_path(job_id, download_dir).unlink(missing_ok=True)


def validate_device_info(device_info: dict[str, Any]) -> None:
    if not device_info:
        raise ValueError("Adding mapping for empty device info: %r" % device_info)
    if not any(device_info.values()):
        raise ValueError(
            "Adding mapping for device info with empty keys: %r" % device_info
        )


def load_mapping_data(filename: Path) -> list[dict[str, Any]]:
    try:
        with open(filename) as f:
            data = yaml_safe_load(f) or []
        if isinstance(data, dict):
            data = [data]
        return data
    except FileNotFoundError:
        return []
