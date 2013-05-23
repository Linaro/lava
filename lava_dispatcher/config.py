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
import os
import StringIO
import logging

from configglue import parser, schema


class DeviceSchema(schema.Schema):
    android_binary_drivers = schema.StringOption()
    cts_media_url = schema.StringOption()
    boot_cmds = schema.StringOption(fatal=True)  # Can do better here
    boot_cmds_android = schema.StringOption(fatal=True)  # And here
    boot_cmds_oe = schema.StringOption(fatal=True)  # And here?
    read_boot_cmds_from_image = schema.BoolOption(default=True)
    boot_options = schema.ListOption()
    boot_linaro_timeout = schema.IntOption(default=300)
    boot_part = schema.IntOption(fatal=True)
    boot_part_android_org = schema.IntOption()
    boot_retries = schema.IntOption(default=3)
    bootloader_prompt = schema.StringOption()
    cache_part_android_org = schema.IntOption()
    client_type = schema.StringOption()
    connection_command = schema.StringOption(fatal=True)
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
    lmc_dev_arg = schema.StringOption()
    master_str = schema.StringOption(default="root@master")
    pre_connect_command = schema.StringOption()
    qemu_drive_interface = schema.StringOption()
    qemu_machine_type = schema.StringOption()
    power_on_cmd = schema.StringOption()  # for sdmux
    power_off_cmd = schema.StringOption()  # for sdmux
    reset_port_command = schema.StringOption()
    root_part = schema.IntOption()
    sdcard_part_android = schema.IntOption()
    sdcard_part_android_org = schema.IntOption()
    soft_boot_cmd = schema.StringOption(default="reboot")
    sys_part_android = schema.IntOption()
    sys_part_android_org = schema.IntOption()
    val = schema.StringOption()
    sdcard_mountpoint_path = schema.StringOption(default="/storage/sdcard0")
    possible_partitions_files = schema.ListOption(default=["init.partitions.rc",
                                                           "fstab.partitions",
                                                           "init.rc"])
    boot_files = schema.ListOption(default=['boot.txt', 'uEnv.txt'])
    boot_device = schema.IntOption(fatal=True)
    testboot_offset = schema.IntOption(fatal=True)
    # see doc/sdmux.rst for details
    sdmux_id = schema.StringOption()
    sdmux_version = schema.StringOption(default="unknown")

    simulator_version_command = schema.StringOption()
    simulator_command = schema.StringOption()
    simulator_axf_files = schema.ListOption()

    android_disable_suspend = schema.BoolOption(default=True)
    android_adb_over_usb = schema.BoolOption(default=False)
    android_adb_over_tcp = schema.BoolOption(default=True)
    android_adb_port = schema.StringOption(default="5555")
    android_wait_for_home_screen = schema.BoolOption(default=True)
    android_wait_for_home_screen_activity = schema.StringOption(default="Displayed com.android.launcher/com.android.launcher2.Launcher:")
    android_home_screen_timeout = schema.IntOption(default=1800)
    android_boot_prompt_timeout = schema.IntOption(default=1200)
    android_orig_block_device = schema.StringOption(default="mmcblk0")
    android_lava_block_device = schema.StringOption(default="mmcblk0")
    partition_padding_string_org = schema.StringOption(default="p")
    partition_padding_string_android = schema.StringOption(default="p")

    arm_probe_binary = schema.StringOption(default='/usr/local/bin/arm-probe')
    arm_probe_config = schema.StringOption(default='/usr/local/etc/arm-probe-config')
    arm_probe_channels = schema.ListOption(default=['VDD_VCORE1'])

    adb_command = schema.StringOption()
    fastboot_command = schema.StringOption()
    shared_working_directory = schema.StringOption(default=None)

    uefi_image_filename = schema.StringOption(default=None)
    vexpress_uefi_path = schema.StringOption(default=None)
    vexpress_uefi_backup_path = schema.StringOption(default=None)
    vexpress_stop_autoboot_prompt = schema.StringOption(
        default='Press Enter to stop auto boot...')
    vexpress_usb_mass_storage_device = schema.StringOption(default=None)

    ecmeip = schema.StringOption()

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
    default_qemu_binary = schema.StringOption(default="qemu")
    lava_cachedir = schema.StringOption()
    lava_cookies = schema.StringOption()
    lava_image_tmpdir = schema.StringOption()
    lava_image_url = schema.StringOption()
    lava_proxy = schema.StringOption()
    lava_result_dir = schema.StringOption()
    lava_server_ip = schema.StringOption(fatal=True)
    lava_test_deb = schema.StringOption()
    lava_test_url = schema.StringOption()
    logging_level = schema.IntOption()


class DispatcherConfig(object):

    def __init__(self, cp, config_dir):
        self.cp = cp
        self.config_dir = config_dir

    for option in DispatcherSchema().options():
        locals()[option.name] = OptionDescriptor(option.name)


default_config_path = os.path.join(
    os.path.dirname(__file__), 'default-config')


def load_config_paths(name, config_dir):
    if config_dir is None:
        paths = [
            os.path.join(path, name) for path in [
                os.path.expanduser("~/.config"),
                "/etc/xdg",
                default_config_path]]
    else:
        paths = [config_dir, os.path.join(default_config_path, name)]
    for path in paths:
        if os.path.isdir(path):
            yield path


def _read_into(path, cp):
    s = StringIO.StringIO()
    s.write('[__main__]\n')
    s.write(open(path).read())
    s.seek(0)
    cp.readfp(s)


def _get_config(name, config_dir, cp):
    """Read a config file named name + '.conf'.

    This checks and loads files from the source tree, site wide location and
    home directory -- in that order, so home dir settings override site
    settings which override source settings.
    """
    config_files = []
    for directory in load_config_paths('lava-dispatcher', config_dir):
        path = os.path.join(directory, '%s.conf' % name)
        if os.path.exists(path):
            config_files.append(path)
    if not config_files:
        raise Exception("no config files named %r found" % (name + ".conf"))
    config_files.reverse()
    logging.debug("About to read %s", str(config_files))
    for path in config_files:
        _read_into(path, cp)
    return cp


def get_config(config_dir):
    cp = parser.SchemaConfigParser(DispatcherSchema())
    _get_config("lava-dispatcher", config_dir, cp)
    valid, report = cp.is_valid(report=True)
    if not valid:
        logging.warning("dispatcher config is not valid:\n    %s", '\n    '.join(report))
    return DispatcherConfig(cp, config_dir)


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


def get_device_config(name, config_dir):
    # We read the device config once to get the device type, then we start
    # again and read device-defaults, device-types/$device-type and
    # devices/$device in that order.
    initial_config = ConfigParser()
    _get_config("devices/%s" % name, config_dir, initial_config)

    real_device_config = parser.SchemaConfigParser(DeviceSchema())
    _get_config("device-defaults", config_dir, real_device_config)
    _get_config(
        "device-types/%s" % initial_config.get('__main__', 'device_type'),
        config_dir, real_device_config)
    _get_config("devices/%s" % name, config_dir, real_device_config)
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


def get_devices(config_dir):
    devices = []
    devices_dir = os.path.join(config_dir, 'devices')
    for d in os.listdir(devices_dir):
        d = os.path.splitext(d)[0]
        devices.append(get_device_config(d, config_dir))
    return devices
