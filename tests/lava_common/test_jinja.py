# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later
from __future__ import annotations

from unittest import TestCase

from lava_common.jinja import create_device_templates_env, qemu_guest_fs_interface
from lava_common.yaml import yaml_safe_load


class TestQemuGuestFsInterface(TestCase):
    """Tests for the qemu_guest_fs_interface Jinja2 filter."""

    # x86 architectures default to ide (legacy PC has an IDE controller)
    def test_x86_archs_default_ide(self) -> None:
        for arch in ("amd64", "x86_64", "i386"):
            self.assertEqual(qemu_guest_fs_interface(arch, None), "ide")

    # non-x86 architectures default to virtio
    def test_non_x86_archs_default_virtio(self) -> None:
        for arch in ("arm64", "aarch64", "arm", "riscv64", "riscv32", "ppc64le"):
            self.assertEqual(qemu_guest_fs_interface(arch, None), "virtio")

    # explicit guestfs_interface always wins
    def test_override_with_guestfs_interface(self) -> None:
        self.assertEqual(qemu_guest_fs_interface("amd64", "scsi"), "scsi")
        self.assertEqual(qemu_guest_fs_interface("arm64", "scsi"), "scsi")
        self.assertEqual(qemu_guest_fs_interface("amd64", "virtio"), "virtio")
        self.assertEqual(qemu_guest_fs_interface("arm64", "ide"), "ide")

    # empty string guestfs_interface falls through to default
    def test_empty_guestfs_interface_falls_through(self) -> None:
        self.assertEqual(qemu_guest_fs_interface("amd64", ""), "ide")
        self.assertEqual(qemu_guest_fs_interface("arm64", ""), "virtio")

    # None guestfs_interface falls through to default
    def test_none_guestfs_interface_falls_through(self) -> None:
        self.assertEqual(qemu_guest_fs_interface("amd64", None), "ide")
        self.assertEqual(qemu_guest_fs_interface("arm64", None), "virtio")


class TestYamlQuoteUndefined(TestCase):
    def test_yaml_quote_undefined(self) -> None:
        jinja_env = create_device_templates_env()
        template = jinja_env.from_string("foo: {{ bar|yaml_quote }}")

        self.assertEqual(yaml_safe_load(template.render()), {"foo": None})
        self.assertEqual(yaml_safe_load(template.render(bar="b: ar")), {"foo": "b: ar"})
