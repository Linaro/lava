Description
###########

Summary
*******

Mocks ``lxc-info`` command used by Linaro Automated Validation Architecture
(LAVA). LXC is Linux Containers userspace tools. ``lxc-info`` does not
use LXC. It is part of ``lava-lxc-mocker``, which mocks some of the LXC
commands used by LAVA.

SYNOPSIS
********

lxc-info {-n name} [-s] [-i]

Options
*******

  -n NAME             Use container identifier NAME. The container identifier
                      format is an alphanumeric string. It creates a directory
                      /var/lib/lxc/NAME and creates symbolic link
                      /var/lib/lxc/NAME/rootfs with target as / (the root)

optional argument:
  -s                  Always prints the container's state as RUNNING

  -i                  Always prints the container's IP address as 0.0.0.0

``lxc-info`` accepts the above options. Any other option specified other than
the above, will be ignored.

Examples
********

To see the mock container's state, use
  lxc-info -sH -n container

To see the mock container's IP address, use
  lxc-info -iH -n container

The 'H' option given above is ignored.

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
lxc-device(1), lxc-start(1), lxc-stop(1)

License
*******
Released under the MIT License:
http://www.opensource.org/licenses/mit-license.php
