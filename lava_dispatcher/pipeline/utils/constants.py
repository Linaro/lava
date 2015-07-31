# Copyright (C) 2014 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA Dispatcher.
#
# LAVA Dispatcher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA Dispatcher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

# Overrides are only supported when and as declared in the comments for
# each constant.

# Delay between each character sent to the shell. This is required for some
# slow serial consoles.
SHELL_SEND_DELAY = 0.05

# Default timeout for shell operations
SHELL_DEFAULT_TIMEOUT = 60

# Default timeout when downloading over http/https
HTTP_DOWNLOAD_TIMEOUT = 15

# Retry at most 5 times
MAX_RETRY = 5

# u-boot auto boot prompt
UBOOT_AUTOBOOT_PROMPT = "Hit any key to stop autoboot"

# u-boot default timeout for commands
UBOOT_DEFAULT_CMD_TIMEOUT = 90

# Ramdisk default filenames
RAMDISK_COMPRESSED_FNAME = 'ramdisk.cpio.gz'
RAMDISK_FNAME = 'ramdisk.cpio'

# Size of the chunks when copying file
FILE_DOWNLOAD_CHUNK_SIZE = 32768

# Size of the chunks when downloading over http
HTTP_DOWNLOAD_CHUNK_SIZE = 32768

# Size of the chunks when downloading over scp
SCP_DOWNLOAD_CHUNK_SIZE = 32768

# Clamp on the maximum timeout allowed for overrides
OVERRIDE_CLAMP_DURATION = 300

# Auto-login prompt timeout default
AUTOLOGIN_DEFAULT_TIMEOUT = 120

# dispatcher temporary directory
# This is distinct from the TFTP daemon directory
# Files here are for download using the Apache /tmp alias.
DISPATCHER_DOWNLOAD_DIR = "/var/lib/lava/dispatcher/tmp"

# OS shutdown message
# Override: set as the shutdown-message parameter of an Action.
SHUTDOWN_MESSAGE = 'The system is going down for reboot NOW'

# Kernel starting message
BOOT_MESSAGE = 'Booting Linux'

# LAVA Coordinator setup and finalize timeout
LAVA_MULTINODE_SYSTEM_TIMEOUT = 90

# Default Action timeout
ACTION_TIMEOUT = 30
