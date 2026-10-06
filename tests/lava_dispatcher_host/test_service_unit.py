# Copyright (C) 2026 Linaro Limited
#
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_precompiled_bpf_and_sandbox_stay_paired():
    # Device sharing loads a pre-compiled BPF object with bpftool, so
    # nothing is compiled on the host and the daemon keeps
    # ProtectKernelModules=true. The sandbox option, the installed object
    # and the bpftool dependency have to stay in sync: lose one and device
    # sharing breaks on fresh installs, or the 85427a5091 hardening
    # regresses.
    unit = (ROOT / "etc" / "lava-dispatcher-host.service").read_text()
    assert "ProtectKernelModules=true" in unit
    # The package must ship the object the code loads.
    setup_py = (ROOT / "setup.py").read_text()
    assert "lava_device_filter.bpf.o" in setup_py
    control = (ROOT / "debian" / "control").read_text()
    # Scope to the package's Depends:, not the whole file: bpftool also
    # appears in Build-Depends: and would match there.
    depends = control.split("Package: lava-dispatcher-host\n")[1]
    assert "bpftool" in depends.split("\nRecommends:")[0]


def test_kheaders_workaround_stays_gone():
    # The kheaders preload and the linux-headers Recommends only existed
    # because bcc compiled the program at runtime. With the pre-compiled
    # object they are dead weight (and an attack surface): keep them out.
    assert not (ROOT / "etc" / "lava-dispatcher-host-modules.conf").exists()
    postinst = (ROOT / "debian" / "lava-dispatcher-host.postinst").read_text()
    assert "kheaders" not in postinst
    control = (ROOT / "debian" / "control").read_text()
    assert "linux-headers" not in control
    assert "python3-bpfcc" not in control
