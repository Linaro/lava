# Copyright (C) 2011 Linaro Limited
#
# Author: Paul Larson <paul.larson@linaro.org>
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

from ConfigParser import ConfigParser
from lava.tool.errors import CommandError
import os
import StringIO
import logging
import commands

from configglue import parser, schema


class DeviceSchema(schema.Schema):
    master_testboot_dir = schema.StringOption()
    master_testboot_label = schema.StringOption()
    master_testrootfs_dir = schema.StringOption()
    master_testrootfs_label = schema.StringOption()
    master_sdcard_dir = schema.StringOption()
    master_sdcard_label = schema.StringOption()
    master_userdata_dir = schema.StringOption()
    master_userdata_label = schema.StringOption()
    android_binary_drivers = schema.StringOption(default=None)
    android_ramdisk_files = schema.ListOption(default=["uInitrd",
                                                       "ramdisk.img"])
    android_init_files = schema.ListOption(default=["init.rc",
                                                    "init.environ.rc"])
    boot_cmds = schema.StringOption(fatal=True)  # Can do better here
    boot_cmds_android = schema.StringOption(fatal=True)  # And here
    boot_cmds_oe = schema.StringOption(fatal=True)  # And here?
    boot_cmds_master = schema.StringOption()  # Optional
    read_boot_cmds_from_image = schema.BoolOption(default=True)
    boot_options = schema.ListOption()
    boot_linaro_timeout = schema.IntOption(default=300)
    boot_part = schema.IntOption(fatal=True)
    boot_part_android_org = schema.IntOption()
    boot_retries = schema.IntOption(default=3)
    bootloader_prompt = schema.StringOption()
    send_char = schema.BoolOption(default=True)
    test_image_prompts = schema.ListOption(default=["\(initramfs\)",
                                                    "linaro-test",
                                                    "root@android",
                                                    "root@linaro",
                                                    "root@master",
                                                    "root@linaro-nano:~#",
                                                    "root@linaro-developer:~#",
                                                    "root@linaro-server:~#",
                                                    "root@genericarmv7a:~#",
                                                    "root@genericarmv8:~#"])
    busybox_http_port = schema.IntOption(default=80)
    cache_part_android_org = schema.IntOption()
    client_type = schema.StringOption()
    connection_command = schema.StringOption(fatal=True)
    connection_command_pattern = schema.StringOption(default="Connected\.\r")
    data_part_android = schema.IntOption()
    data_part_android_org = schema.IntOption()
    default_network_interface = schema.StringOption()
    disablesuspend_timeout = schema.IntOption(default=240)
    device_type = schema.StringOption(fatal=True)
    enable_network_after_boot_android = schema.BoolOption(default=True)
    git_url_disablesuspend_sh = schema.StringOption()
    hard_reset_command = schema.StringOption()
    hostname = schema.StringOption()
    image_boot_msg = schema.StringOption()
    interrupt_boot_command = schema.StringOption()
    interrupt_boot_prompt = schema.StringOption()
    interrupt_boot_control_character = schema.StringOption()
    bootloader_serial_delay_ms = schema.IntOption(default=0)
    test_shell_serial_delay_ms = schema.IntOption(default=0)
    lmc_dev_arg = schema.StringOption()
    master_str = schema.StringOption(default="root@master")
    pre_connect_command = schema.StringOption()
    qemu_binary = schema.StringOption(default="qemu-system-arm")
    qemu_options = schema.StringOption()
    qemu_drive_interface = schema.StringOption()
    qemu_machine_type = schema.StringOption()
    power_on_cmd = schema.StringOption()  # for sdmux
    power_off_cmd = schema.StringOption()  # for sdmux
    reset_port_command = schema.StringOption()
    root_part = schema.IntOption()
    sata_block_device = schema.StringOption(default="sda")
    sdcard_part_android = schema.IntOption()
    sdcard_part_android_org = schema.IntOption()
    soft_boot_cmd = schema.StringOption(default="reboot")
    sys_part_android = schema.IntOption()
    sys_part_android_org = schema.IntOption()
    tester_ps1 = schema.StringOption(null=True)
    tester_ps1_pattern = schema.StringOption(null=True)
    ve_uefi_flash_msg = schema.StringOption(default="Erasing Flash image uefi")

    # tester_ps1_includes_rc is a string so we can decode it later as yes/no/
    # not set. If it isn't set, we stick with the device default. We can't do
    # the tri-state logic as a BoolOption.
    tester_ps1_includes_rc = schema.StringOption(null=True)

    tester_rc_cmd = schema.StringOption(null=True)
    lava_test_dir = schema.StringOption(null=True)
    val = schema.StringOption()
    sdcard_mountpoint_path = schema.StringOption(default="/storage/sdcard0")
    possible_partitions_files = schema.ListOption(default=["init.partitions.rc",
                                                           "fstab.partitions",
                                                           "init.rc"])
    boot_files = schema.ListOption(default=['boot.txt', 'uEnv.txt'])
    boot_device = schema.IntOption(fatal=True)
    testboot_offset = schema.IntOption(fatal=True)
    # see doc/sdmux.rst for details

    lmp_default_id = schema.StringOption(default="13060000")
    lmp_default_name = schema.StringOption(default="default")

    sdmux_id = schema.StringOption()
    sdmux_usb_id = schema.StringOption()
    sdmux_mount_retry_seconds = schema.IntOption(default=20)
    sdmux_mount_wait_seconds = schema.IntOption(default=10)
    sdmux_version = schema.StringOption(default="unknown")

    # for the HDMI module of LMP
    lmp_hdmi_id = schema.DictOption()
    lmp_hdmi_version = schema.StringOption(default="unknown")

    # for the SATA module of LMP
    lmp_sata_id = schema.DictOption()
    lmp_sata_version = schema.StringOption(default="unknown")

    # for the ETH module of LMP
    lmp_eth_id = schema.DictOption()
    lmp_eth_version = schema.StringOption(default="unknown")

    # for the LSGPIO module of LMP
    lmp_lsgpio_id = schema.DictOption()
    lmp_lsgpio_version = schema.StringOption(default="unknown")

    # for the USB module of LMP
    lmp_usb_id = schema.DictOption()
    lmp_usb_version = schema.StringOption(default="unknown")

    # auto image login
    login_prompt = schema.StringOption(default=None)
    password_prompt = schema.StringOption(default=None)
    username = schema.StringOption(default=None)
    password = schema.StringOption(default=None)
    login_commands = schema.ListOption(default=None)

    simulator_version_command = schema.StringOption()
    simulator_command = schema.StringOption()
    simulator_command_flag = schema.StringOption(default=" -C ")
    simulator_axf_files = schema.ListOption()
    simulator_kernel_files = schema.ListOption(default=None)
    simulator_kernel = schema.StringOption(default=None)
    simulator_initrd_files = schema.ListOption(default=None)
    simulator_initrd = schema.StringOption(default=None)
    simulator_dtb_files = schema.ListOption(default=None)
    simulator_dtb = schema.StringOption(default=None)
    simulator_uefi_files = schema.ListOption(default=None)
    simulator_bl1_files = schema.ListOption(default=None)
    simulator_bl1 = schema.StringOption(default=None)
    simulator_bl2_files = schema.ListOption(default=None)
    simulator_bl2 = schema.StringOption(default=None)
    simulator_bl31_files = schema.ListOption(default=None)
    simulator_bl31 = schema.StringOption(default=None)
    simulator_boot_wrapper = schema.StringOption(default=None)

    android_disable_suspend = schema.BoolOption(default=True)
    android_adb_over_usb = schema.BoolOption(default=False)
    android_adb_over_tcp = schema.BoolOption(default=True)
    android_adb_port = schema.StringOption(default="5555")
    android_wait_for_home_screen = schema.BoolOption(default=True)
    android_wait_for_home_screen_activity = schema.StringOption(
        default="Displayed com.android.launcher/com.android.launcher2.Launcher:")
    android_home_screen_timeout = schema.IntOption(default=1800)
    android_boot_prompt_timeout = schema.IntOption(default=1200)
    android_orig_block_device = schema.StringOption(default="mmcblk0")
    android_lava_block_device = schema.StringOption(default="mmcblk0")
    partition_padding_string_org = schema.StringOption(default="p")
    partition_padding_string_android = schema.StringOption(default="p")

    arm_probe_binary = schema.StringOption(default='/usr/local/bin/arm-probe')
    arm_probe_config = schema.StringOption(default='/usr/local/etc/arm-probe-config')
    arm_probe_channels = schema.ListOption(default=['VDD_VCORE1'])

    uefi_image_filename = schema.StringOption(default=None)
    customize = schema.DictOption(default=None)
    vexpress_uefi_path = schema.StringOption(default=None)
    vexpress_uefi_backup_path = schema.StringOption(default=None)
    vexpress_stop_autoboot_prompt = schema.StringOption(
        default='Press Enter to stop auto boot...')
    vexpress_usb_mass_storage_device = schema.StringOption(default=None)

    bl1_image_files = schema.ListOption(default=None)
    bl1_image_filename = schema.StringOption(default="bl1.bin")
    fip_image_files = schema.ListOption(default=None)
    fip_image_filename = schema.StringOption(default="fip.bin")

    wg_bl1_path = schema.StringOption(default="SOFTWARE/bl1.bin")
    wg_fip_path = schema.StringOption(default="SOFTWARE/fip.bin")

    wg_bl1_backup_path = schema.StringOption(default="SOFTWARE/backup-bl1.bin")
    wg_fip_backup_path = schema.StringOption(default="SOFTWARE/backup-fip.bin")

    wg_usb_mass_storage_device = schema.StringOption(default="/dev/disk/by-label/WG")
    wg_stop_autoboot_prompt = schema.StringOption(
        default='Press Enter to stop auto boot...')

    ecmeip = schema.StringOption()
    ipmi_power_sleep = schema.IntOption(default=1)
    ipmi_power_retries = schema.IntOption(default=10)

    # for dummy devices
    dummy_driver = schema.StringOption(default=None)
    dummy_schroot_chroot = schema.StringOption(default="default")
    dummy_ssh_host = schema.StringOption(default=None)
    dummy_ssh_port = schema.IntOption(default=22)
    dummy_ssh_username = schema.StringOption(default='root')
    dummy_ssh_identity_file = schema.StringOption(default=None)

    # for jtag devices
    jtag_driver = schema.StringOption(default=None)
    jtag_hard_reset_command = schema.StringOption(default=None)
    jtag_hard_reset_sleep = schema.IntOption(default=60)
    # for stmc devices
    jtag_stmc_boot_script = schema.StringOption(default=None)
    jtag_stmc_boot_options = schema.StringOption(default=None)
    jtag_stmc_kernel_command = schema.StringOption(default=None)
    jtag_stmc_ramdisk_command = schema.StringOption(default=None)
    jtag_stmc_dtb_command = schema.StringOption(default=None)

    # for fastboot devices
    fastboot_driver = schema.StringOption(default=None)
    adb_command = schema.StringOption()
    fastboot_command = schema.StringOption()
    fastboot_kernel_load_addr = schema.StringOption()
    rootfs_partition = schema.StringOption(default='userdata')
    shared_working_directory = schema.StringOption(default=None)

    # for bootloader devices
    pre_boot_cmd = schema.StringOption()
    use_lava_tmpdir = schema.BoolOption(default=True)
    alternative_create_tmpdir = schema.BoolOption(default=True)
    alternative_dir = schema.StringOption(default=None)
    u_load_addrs = schema.ListOption(default=None)
    z_load_addrs = schema.ListOption(default=None)

    # for dynamic_vm devices
    dynamic_vm_backend_device_type = schema.StringOption(default='kvm')
    dynamic_vm_host = schema.StringOption(default=None)


class OptionDescriptor(object):
    def __init__(self, name):
        self.name = name

    def __get__(self, inst, cls=None):
        return inst.cp.get('__main__', self.name)


class DeviceConfig(object):

    def __init__(self, cp):
        self.cp = cp

    for option in DeviceSchema().options():
        locals()[option.name] = OptionDescriptor(option.name)


class DispatcherSchema(schema.Schema):
    lava_cachedir = schema.StringOption()
    lava_cookies = schema.StringOption()
    lava_image_tmpdir = schema.StringOption()
    lava_image_url = schema.StringOption()
    lava_proxy = schema.StringOption()
    lava_result_dir = schema.StringOption()
    lava_server_ip = schema.StringOption()
    lava_network_iface = schema.ListOption()
    lava_test_deb = schema.StringOption()
    lava_test_url = schema.StringOption()
    logging_level = schema.IntOption()
    host_command_retries = schema.IntOption(default=5)


class DispatcherConfig(object):

    def __init__(self, cp):
        self.cp = cp

    for option in DispatcherSchema().options():
        locals()[option.name] = OptionDescriptor(option.name)


user_config_path = os.path.expanduser("~/.config/lava-dispatcher")

if "VIRTUAL_ENV" in os.environ:
    system_config_path = os.path.join(os.environ["VIRTUAL_ENV"],
                                      "etc/lava-dispatcher")
else:
    system_config_path = "/etc/lava-dispatcher"

deprecated_system_config_path = "/etc/xdg/lava-dispatcher"

default_config_path = os.path.join(os.path.dirname(__file__),
                                   'default-config/lava-dispatcher')

custom_config_path = None
custom_config_file = None


def search_path():
    if custom_config_path:
        return [
            custom_config_path,
            default_config_path,
        ]
    else:
        return [
            user_config_path,
            system_config_path,
            default_config_path,
        ]


def write_path():
    """
    Returns the configuration directories where configuration files should be
    written to.

    Returns an array with a list of directories. Client tools should then write
    any configuration files to the first directory in that list that is
    writable by the user.
    """
    if custom_config_path:
        return [custom_config_path]
    else:
        # Since usually you need to run the dispatcher as root, but lava-tool
        # as a regular user, we give preference to writing to the system
        # configuration to avoid the user writing config file to ~user, and the
        # dispatcher looking for them at ~root.
        return [system_config_path, user_config_path]


def _read_into(path, cp):
    s = StringIO.StringIO()
    s.write('[__main__]\n')
    s.write(open(path).read())
    s.seek(0)
    cp.readfp(s)


def _get_config(name, cp):
    """Read a config file named name + '.conf'.

    This checks and loads files from the source tree, site wide location and
    home directory -- in that order, so home dir settings override site
    settings which override source settings.
    """
    config_files = []
    for directory in search_path():
        path = os.path.join(directory, '%s.conf' % name)
        if os.path.exists(path):
            config_files.append(path)
    if not config_files and not custom_config_file:
        raise Exception("no config files named %r found" % (name + ".conf"))
    config_files.reverse()
    for path in config_files:
        _read_into(path, cp)
    return cp


def _lookup_ip(lava_network_iface):
    for iface in lava_network_iface:
        line = commands.getoutput("ip address show dev %s" % iface).split()
        if 'inet' in line:
            return line[line.index('inet') + 1].split('/')[0]
    raise CommandError("LAVA_NETWORK_IFACE is set to '%s' "
                       "but no IP address was found for any listed interface." % ", ".join(lava_network_iface))


def get_config():
    cp = parser.SchemaConfigParser(DispatcherSchema())
    _get_config("lava-dispatcher", cp)
    valid, report = cp.is_valid(report=True)
    if not valid:
        logging.warning("dispatcher config is not valid:\n    %s", '\n    '.join(report))
    config = DispatcherConfig(cp)
    if config.lava_network_iface:
        config.lava_server_ip = _lookup_ip(config.lava_network_iface)
        config.lava_image_url = cp.get('__main__', "LAVA_IMAGE_URL", vars={'LAVA_SERVER_IP': config.lava_server_ip})
    return config


def _hack_boot_options(scp):
    """
    Boot options are built by creating sections for each item in the
    boot_options list. Those sections are managed by
    lava_dispatcher.device.boot_options so we ignore here
    """
    scp.extra_sections = set(scp.get('__main__', 'boot_options'))


def _hack_report(report):
    """
    ConfigGlue makes warning for somethings we don't want to warn about. In
    particular, it will warn if a value isn't known to the config such as
    in the case where you are using config variables or where you define
    something like a boot_option for master like "boot_cmds_fdt"
    """
    scrubbed = []
    ignores = [
        'Configuration includes invalid options for section',
    ]
    for err in report:
        for ignore in ignores:
            if not err.startswith(ignore):
                scrubbed.append(err)
    return scrubbed


def get_device_config(name, backend_device_type=None):
    # We read the device config once to get the device type, then we start
    # again and read device-defaults, device-types/$device-type and
    # devices/$device in that order.
    initial_config = ConfigParser()
    _get_config("devices/%s" % name, initial_config)
    if custom_config_file:
        _read_into(custom_config_file, initial_config)

    device_type = initial_config.get('__main__', 'device_type')

    real_device_config = parser.SchemaConfigParser(DeviceSchema())
    _get_config("device-defaults", real_device_config)

    client_type = None
    if backend_device_type:
        _get_config("device-types/%s" % backend_device_type, real_device_config)
        client_type = real_device_config.get('__main__', 'client_type')

    _get_config("device-types/%s" % device_type, real_device_config)

    if backend_device_type:
        real_device_config.set('__main__', 'device_type', backend_device_type)
        real_device_config.set('__main__', 'client_type', client_type)

    _get_config("devices/%s" % name, real_device_config)
    if custom_config_file:
        _read_into(custom_config_file, real_device_config)
    real_device_config.set("__main__", "hostname", name)
    _hack_boot_options(real_device_config)
    valid, report = real_device_config.is_valid(report=True)
    if not valid:
        report = _hack_report(report)
        if len(report) > 0:
            report = '\n    '.join(report)
            logging.warning(
                "Device config for %s is not valid:\n    %s", name, report)

    return DeviceConfig(real_device_config)


def list_devices():
    devices = []
    for config_dir in search_path():
        devices_dir = os.path.join(config_dir, 'devices')
        if os.path.isdir(devices_dir):
            for d in os.listdir(devices_dir):
                if d.endswith('.conf'):
                    d = os.path.splitext(d)[0]
                    devices.append(d)
    return devices


def get_devices():
    return [get_device_config(d) for d in list_devices()]


def get_config_file(config_file):
    for config_dir in search_path():
        config_file_path = os.path.join(config_dir, config_file)
        if os.path.exists(config_file_path):
            return config_file_path
    return None
