# Copyright (C) 2022 Linaro Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
