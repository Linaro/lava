Description
###########

Summary
*******

``lava-lxc-mocker`` is a collection of mocker scripts that mocks each of
the LXC command that Linaro Automated Validation Architecture (LAVA) uses.
It does not support all commands and options that lxc provides, but just the
ones that LAVA uses. LAVA Test jobs using LXC can then be replicated in
Docker with the help of ``lava-lxc-mocker``.

List of mocked commands
***********************

* lxc-attach
* lxc-create
* lxc-destroy
* lxc-device
* lxc-info
* lxc-start
* lxc-stop

NOTE
****
LXC is Linux Containers userspace tools. ``lava-lxc-mocker`` does not
use LXC. The commands provided by ``lava-lxc-mocker`` are simple shell scripts
that use the same command names mocking some LXC commands. ``lava-lxc-mocker``
commands still need to be executed in the same sequence as a typical LXC
operation. In particular, once a container has been created, that container
needs to be destroyed to clean up the symlinks and other artifacts.

See Also
********
lxc-attach(1), lxc-create(1), lxc-destroy(1), lxc-device(1), lxc-info(1),
lxc-start(1), lxc-stop(1)

License
*******
Released under the MIT License:
http://www.opensource.org/licenses/mit-license.php
