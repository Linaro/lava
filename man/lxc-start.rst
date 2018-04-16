Description
###########

Summary
*******

Mocks ``lxc-start`` command used by Linaro Automated Validation Architecture
(LAVA). LXC is Linux Containers userspace tools. ``lxc-start`` does not
use LXC. It is part of ``lava-lxc-mocker``, which mocks some of the LXC
commands used by LAVA. ``lxc-start`` does not do anything except exiting with 0
(zero).

SYNOPSIS
********

lxc-start

NOTE
****
The commands provided by ``lava-lxc-mocker`` are simple shell scripts that use
the same command names mocking some LXC commands and does not
use LXC. ``lava-lxc-mocker`` commands still need to be executed in the same
sequence as a typical LXC operation. In particular, once a container has been
created, that container needs to be destroyed to clean up the symlinks and
other artifacts.

See Also
********
lava-lxc-mocker(7), lxc-attach(1), lxc-create(1), lxc-destroy(1),
lxc-device(1), lxc-info(1), lxc-stop(1)

License
*******
Released under the MIT License:
http://www.opensource.org/licenses/mit-license.php
