Description
###########

Summary
*******

Mocks ``lxc-create`` command used by Linaro Automated Validation Architecture
(LAVA). LXC is Linux Containers userspace tools. ``lxc-create`` does not
use LXC. It is part of ``lava-lxc-mocker``, which mocks some of the LXC
commands used by LAVA.

SYNOPSIS
********

lxc-create {-n name} [-q] [-- --packages]

Options
*******

  -n NAME             Use container identifier NAME. The container identifier
                      format is an alphanumeric string. It creates a directory
                      /var/lib/lxc/NAME and creates symbolic link
                      /var/lib/lxc/NAME/rootfs with target as / (the root)

optional argument:
  -q                  quite or mute on

  -- --packages=PACKAGE_NAME1,PACKAGE_NAME2,...
                      List of packages to install. Comma separated, without
                      space. Note: this option is prefixed by '-- '

``lxc-create`` accepts the above options. Any other option specified other than
the above, will be ignored.

Examples
********

To create a mock container and install packages, use
  lxc-create -q -t debian -n container -- --release sid --packages
  systemd,systemd-sysv

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
lava-lxc-mocker(7), lxc-attach(1), lxc-destroy(1), lxc-device(1), lxc-info(1),
lxc-start(1), lxc-stop(1)

License
*******
Released under the MIT License:
http://www.opensource.org/licenses/mit-license.php
