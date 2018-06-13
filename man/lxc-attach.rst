Description
###########

Summary
*******

Mocks ``lxc-attach`` command used by Linaro Automated Validation Architecture
(LAVA). LXC is Linux Containers userspace tools. ``lxc-attach`` does not
use LXC. It is part of ``lava-lxc-mocker``, which mocks some of the LXC
commands used by LAVA.

SYNOPSIS
********

lxc-attach {-n name} [-- command]

Options
*******

  -n NAME       Use container identifier NAME. The container identifier format
                is an alphanumeric string. This argument is required, but not
                used.

optional argument:

  -- COMMAND    runs the specified COMMAND that follows '--'
                When no COMMAND is specified, then opens up a shell.

``lxc-attach`` accepts the above options. Any other option specified other than
the above, will be ignored.

Examples
********

To update the package repository, use
  lxc-attach -n container -- apt-get -y -q update

The above will run "apt-get -y -q update" directly on the host.

To open up a shell, use
  lxc-attach -n container

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
lava-lxc-mocker(7), lxc-create(1), lxc-destroy(1), lxc-device(1), lxc-info(1),
lxc-start(1), lxc-stop(1)

License
*******
Released under the MIT License:
http://www.opensource.org/licenses/mit-license.php
