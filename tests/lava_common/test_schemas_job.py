# Copyright (C) 2026 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

import pytest
from voluptuous import Invalid

from lava_common.schemas import validate

MULTINODE_JOB = {
    "job_name": "multinode job",
    "visibility": "public",
    "timeouts": {"job": {"minutes": 10}},
    "protocols": {
        "lava-multinode": {
            "roles": {
                "server": {"device_type": "qemu", "count": 1},
                "client": {"device_type": "qemu", "count": 1},
            }
        }
    },
    "actions": [
        {"boot": {"method": "qemu", "media": "tmpfs", "role": ["server", "client"]}}
    ],
}


def multinode_job(pool_pattern=None):
    job = {
        **MULTINODE_JOB,
        "protocols": {
            "lava-multinode": {**MULTINODE_JOB["protocols"]["lava-multinode"]}
        },
    }
    if pool_pattern is not None:
        job["protocols"]["lava-multinode"]["pool_pattern"] = pool_pattern
    return job


class TestPoolPattern:
    def test_without_pool_pattern(self):
        validate(multinode_job(), strict=True)

    @pytest.mark.parametrize(
        "pool_pattern", ["pool-*", "lab-?", "rack-[0-9]", "rack", "*"]
    )
    def test_valid_pool_patterns(self, pool_pattern):
        validate(multinode_job(pool_pattern), strict=True)

    def test_pool_pattern_should_be_a_string(self):
        with pytest.raises(Invalid):
            validate(multinode_job(42), strict=True)

    def test_pool_pattern_should_not_be_empty(self):
        with pytest.raises(Invalid):
            validate(multinode_job(""), strict=True)

    def test_pool_pattern_is_rejected_at_the_top_level(self):
        job = multinode_job()
        job["pool_pattern"] = "pool-*"
        with pytest.raises(Invalid):
            validate(job, strict=True)


def git_test_job(**params):
    definition = {
        "name": "smoke-tests",
        "from": "git",
        "repository": "https://gitlab.com/lava/functional-tests.git",
        "path": "posix/smoke-tests-basic.yaml",
        **params,
    }
    return {
        "job_name": "git test job",
        "device_type": "qemu",
        "visibility": "public",
        "timeouts": {"job": {"minutes": 10}},
        "actions": [{"test": {"definitions": [definition]}}],
    }


class TestGitDefinition:
    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"branch": "main"},
            {"revision": "441b61"},
            {"shallow": False},
            {"history": False},
            {"recursive": True},
        ],
    )
    def test_valid_git_parameters(self, params):
        validate(git_test_job(**params), strict=True)

    def test_shallow_should_be_a_boolean(self):
        with pytest.raises(Invalid):
            validate(git_test_job(shallow="no"), strict=True)


def secondary_media_boot_job(method, **params):
    boot = {
        "method": method,
        "commands": "sata",
        "kernel": "/boot/vmlinuz",
        "ramdisk": "/boot/initrd.img",
        "dtb": "/boot/board.dtb",
        "root_uuid": "UUID=159d17cc-697c-4125-95a0-a3775e1deabe",
        "boot_part": 1,
        **params,
    }
    return {
        "job_name": "secondary media job",
        "device_type": "mustang",
        "visibility": "public",
        "timeouts": {"job": {"minutes": 10}},
        "actions": [{"boot": boot}],
    }


class TestSecondaryMediaBoot:
    @pytest.mark.parametrize("method", ["grub", "grub-efi"])
    def test_grub(self, method):
        validate(secondary_media_boot_job(method), strict=True)
        validate(secondary_media_boot_job(method, boot_part="(hd0,gpt1)"), strict=True)

    @pytest.mark.parametrize("kernel_type", ["image", "uimage", "zimage"])
    def test_u_boot(self, kernel_type):
        validate(
            secondary_media_boot_job("u-boot", kernel_type=kernel_type), strict=True
        )

    def test_u_boot_invalid_kernel_type(self):
        with pytest.raises(Invalid):
            validate(
                secondary_media_boot_job("u-boot", kernel_type="vmlinux"), strict=True
            )

    def test_kernel_type_is_u_boot_only(self):
        with pytest.raises(Invalid):
            validate(secondary_media_boot_job("grub", kernel_type="image"), strict=True)


def boot_job(boot):
    return {
        "job_name": "boot job",
        "device_type": "qemu",
        "visibility": "public",
        "timeouts": {"job": {"minutes": 10}},
        "actions": [{"boot": boot}],
    }


TRANSFER_OVERLAY = {"download_command": "wget", "unpack_command": "tar -C / -xzf"}


class TestNodebooterBoot:
    def test_valid(self):
        validate(
            boot_job(
                {
                    "method": "nodebooter",
                    "docker": {"image": "nodebooter:latest", "local": True},
                    "prompts": ["root@dut:~#"],
                    "auto_login": {"login_prompt": "login:", "username": "root"},
                    "transfer_overlay": TRANSFER_OVERLAY,
                }
            ),
            strict=True,
        )

    def test_docker_is_required(self):
        with pytest.raises(Invalid):
            validate(boot_job({"method": "nodebooter"}), strict=True)

    @pytest.mark.parametrize(
        "key,value", [("command", "nodebooter"), ("downloads-namespace", "dl")]
    )
    def test_unused_keys_are_rejected(self, key, value):
        boot = {"method": "nodebooter", "docker": {"image": "nodebooter"}, key: value}
        with pytest.raises(Invalid):
            validate(boot_job(boot), strict=True)


class TestUefiBoot:
    def test_transfer_overlay(self):
        validate(
            boot_job(
                {
                    "method": "uefi",
                    "commands": "nfs",
                    "transfer_overlay": TRANSFER_OVERLAY,
                }
            ),
            strict=True,
        )
