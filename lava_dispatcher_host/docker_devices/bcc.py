# Copyright (C) 2022 Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: Apache-2.0

import os

from bcc import BPF as BCCBPF
from bcc import lib


class BPF(BCCBPF):
    # Submitted upstream: https://github.com/iovisor/bcc/pull/3919
    # After that gets merged and is available on versions of `bcc` on all
    # platforms supported by LAVA, this can be dropped.
    def close(self):
        """close(self)

        Closes all associated files descriptors. Attached BPF programs are not
        detached.
        """
        for name, fn in list(self.funcs.items()):
            os.close(fn.fd)
            del self.funcs[name]
        if self.module:  # pylint: disable=access-member-before-definition
            lib.bpf_module_destroy(
                self.module  # pylint: disable=access-member-before-definition
            )
            self.module = None
