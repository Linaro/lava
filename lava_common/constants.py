# Copyright (C) 2014-2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# This file is part of LAVA.
#
# LAVA is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# LAVA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along
# with this program; if not, see <http://www.gnu.org/licenses>.

# Overrides are only supported when and as declared in the comments for
# each constant.

# Retry at most 5 times
MAX_RETRY = 5

# size of u-boot header to be removed from ramdisks, in bytes.
UBOOT_DEFAULT_HEADER_LENGTH = 64

# Ramdisk default filenames
RAMDISK_FNAME = "ramdisk.cpio"

# Size of the chunks when copying file
FILE_DOWNLOAD_CHUNK_SIZE = 32768

# Size of the chunks when downloading over http
HTTP_DOWNLOAD_CHUNK_SIZE = 32768

# Size of the chunks when downloading over scp
SCP_DOWNLOAD_CHUNK_SIZE = 32768

# dispatcher temporary directory
# This is distinct from the TFTP daemon directory
# Files here are for download using the Apache /tmp alias.
DISPATCHER_DOWNLOAD_DIR = "/var/lib/lava/dispatcher/tmp"

# Distinctive prompt characters which can
# help distinguish status messages from shell prompts.
DISTINCTIVE_PROMPT_CHARACTERS = "\\:"

# LAVA Coordinator setup and finalize timeout
LAVA_MULTINODE_SYSTEM_TIMEOUT = 90

# Default Action timeout
ACTION_TIMEOUT = 30

# Android tmp directory
ANDROID_TMP_DIR = "/data/local/tmp"

# LXC protocol name
LXC_PROTOCOL = "lava-lxc"

# LXC container path
LXC_PATH = "/var/lib/lxc"

# LXC finalize timeout
LAVA_LXC_TIMEOUT = 90

# LXC templates with mirror option
LXC_TEMPLATE_WITH_MIRROR = ["debian", "ubuntu"]

# LXC default packages
LXC_DEFAULT_PACKAGES = "systemd,systemd-sysv"

# LAVA home in LXC
LAVA_LXC_HOME = "/lava-lxc"

# mount point for download directory when postprocessing images (e.g. within
# docker containers)
LAVA_DOWNLOADS = "/lava-downloads"

# Timeout used by the vland protocol when waiting for vland to
# respond to the api.create_vlan request, in seconds.
VLAND_DEPLOY_TIMEOUT = 120

# bootloader default timeout for commands
BOOTLOADER_DEFAULT_CMD_TIMEOUT = 90

# kernel boot monitoring
# Some successful kernel builds end the boot with this string
KERNEL_FREE_UNUSED_MSG = r"Freeing unused kernel memory"
# Some successful kernel builds end the boot with this string
KERNEL_FREE_INIT_MSG = r"Freeing init memory"
# exception
KERNEL_EXCEPTION_MSG = r"-+\[ cut here \]-+\s+(.*\s+-+\[ end trace (\w*) \]-+)"
# stack trace
KERNEL_TRACE_MSG = r"Stack:\s+(.*\s+-+\[ end trace (\w*) \]-+)"
# unhandled fault
KERNEL_FAULT_MSG = r"(Unhandled fault.*)\r\n"
# panic
KERNEL_PANIC_MSG = r"Kernel panic - (.*) end Kernel panic"

# Login incorrect message
LOGIN_INCORRECT_MSG = "Login incorrect"
# Login incorrect message
LOGIN_TIMED_OUT_MSG = "Login timed out"

# qemu installer size limit in Mb
# (i.e. size * 1024 * 1024)
INSTALLER_IMAGE_MAX_SIZE = 8 * 1024  # 8Gb
INSTALLER_QUIET_MSG = "Loading initial ramdisk"

# List of DD output prompts for notifying completion of secondary deployment
DD_PROMPTS = [r"[0-9]+\+[0-9]+ records out", r"[0-9]+ bytes \(.*\) copied"]

# fallback UEFI menu label class
DEFAULT_UEFI_LABEL_CLASS = r"a-zA-Z0-9\s\:"

# Set a default newline seperator for pexpect, override as necessary
LINE_SEPARATOR = "\n"
# other newline separators
UEFI_LINE_SEPARATOR = "\r\n"

# valid characters in components of a test definition name
# excludes whitespace and punctuation (except hyphen and underscore)
DEFAULT_TESTDEF_NAME_CLASS = r"^[\w\d\_\-]+$"

# Limit repetitive messages
METADATA_MESSAGE_LIMIT = 8192

# Versatile Express autorun interrupt character
VEXPRESS_AUTORUN_INTERRUPT_CHARACTER = " "

# sys class kvm path
SYS_CLASS_KVM = "/sys/class/misc/kvm"

# default reboot commands
REBOOT_COMMAND_LIST = ["reboot", "reboot -n", "reboot -nf"]

# XNBD server timeout (nbd deploy / xnbd protocol)
XNBD_SYSTEM_TIMEOUT = 10000

# XNBD port range min, default 55000
XNBD_PORT_RANGE_MIN = 55000

# XNBD port range max, default 56000
XNBD_PORT_RANGE_MAX = 56000

# Default size limit for tftp in bytes (4Gb)
TFTP_SIZE_LIMIT = 4 * 1024 * 1024 * 1024

# udev rules directory
UDEV_RULES_DIR = "/etc/udev/rules.d/"

UDEV_RULE_FILENAME = UDEV_RULES_DIR + "99-lava-dispatcher-host.rules"

# Services which allow alternative IP's and ports
VALID_DISPATCHER_IP_PROTOCOLS = ["http", "nfs", "tftp"]
