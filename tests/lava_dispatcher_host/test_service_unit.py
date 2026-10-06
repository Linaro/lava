#
# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_sandbox_and_kernel_header_paths_stay_paired():
    # bcc compiles the device sharing program against kernel headers,
    # either an installed kernel headers package
    # (/lib/modules/$(uname -r)/build) or the kheaders module on kernels
    # that build it. The sandboxed daemon cannot load modules, so
    # kheaders is preloaded at boot. The sandbox option, the preload and
    # the packaging have to stay in sync: if one goes missing, device
    # sharing breaks on fresh installs or the 85427a5091 hardening
    # regresses.
    unit = (ROOT / "etc" / "lava-dispatcher-host.service").read_text()
    assert "ProtectKernelModules=true" in unit
    modules_conf = (ROOT / "etc" / "lava-dispatcher-host-modules.conf").read_text()
    assert "kheaders" in modules_conf.split()
    # The conf is only effective if the package installs it.
    setup_py = (ROOT / "setup.py").read_text()
    assert "lava-dispatcher-host-modules.conf" in setup_py
    control = (ROOT / "debian" / "control").read_text()
    assert "linux-headers" in control
