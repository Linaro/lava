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

from ConfigParser import ConfigParser, NoOptionError
import os
import StringIO
import logging


from configglue import parser, schema

_sentinel = object()


class ConfigWrapper(object):
    def __init__(self, cp):
        self.cp = cp

    def get(self, key, default=_sentinel):
        try:
            val = self.cp.get("__main__", key)
            if default is not _sentinel and val == '':
                val = default
            return val
        except NoOptionError:
            if default is not _sentinel:
                return default
            else:
                raise

class DeviceSchema(schema.Schema):
    android_binary_drivers = schema.StringOption()
    boot_cmds = schema.StringOption(fatal=True) # Can do better here
    boot_cmds_android = schema.StringOption(fatal=True) # And here
    boot_cmds_oe = schema.StringOption(fatal=True) # And here?
    boot_linaro_timeout = schema.IntOption(default=300)
    boot_part = schema.IntOption(fatal=True)
    boot_part_android_org = schema.StringOption()
    bootloader_prompt = schema.StringOption()
    cache_part_android_org = schema.StringOption()
    client_type = schema.StringOption()
    connection_command = schema.StringOption(fatal=True)
    data_part_android = schema.StringOption()
    data_part_android_org = schema.StringOption()
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
    master_str = schema.StringOption()
    pre_connect_command = schema.StringOption()
    qemu_drive_interface = schema.StringOption()
    qemu_machine_type = schema.StringOption()
    reset_port_command = schema.StringOption()
    root_part = schema.IntOption()
    sdcard_part_android = schema.StringOption()
    sdcard_part_android_org = schema.StringOption()
    soft_boot_cmd = schema.StringOption()
    sys_part_android = schema.StringOption()
    sys_part_android_org = schema.StringOption()
    tester_hostname = schema.StringOption(default="linaro")
    tester_str = schema.StringOption()
    val = schema.StringOption()

    simulator_binary = schema.StringOption()
    license_server = schema.StringOption()

class OptionDescriptor(object):
    def __init__(self, name):
        self.name = name
    def __get__(self, inst, cls=None):
        return inst.get(self.name)


class DeviceConfig(ConfigWrapper):
    for option in DeviceSchema().options():
        locals()[option.name] = OptionDescriptor(option.name)


class DispatcherSchema(schema.Schema):
    default_qemu_binary = schema.StringOption(default="qemu")
    lava_cachedir = schema.StringOption()
    lava_image_tmpdir = schema.StringOption()
    lava_image_url = schema.StringOption()
    lava_proxy = schema.StringOption()
    lava_result_dir = schema.StringOption()
    lava_server_ip = schema.StringOption(fatal=True)
    lava_test_deb = schema.StringOption()
    lava_test_url = schema.StringOption()
    logging_level = schema.IntOption()


class DispatcherConfig(ConfigWrapper):
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


def _get_config(name, config_dir, cp=None, schema=None):
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
    if cp is None:
        if schema:
            cp = parser.SchemaConfigParser(schema)
        else:
            cp = ConfigParser()
    logging.debug("About to read %s" % str(config_files))
    for path in config_files:
        _read_into(path, cp)
    return cp

def get_config(config_dir):
    cp = _get_config("lava-dispatcher", config_dir, schema=DispatcherSchema())
    valid, report = cp.is_valid(report=True)
    if not valid:
        logging.warning("dispatcher config is not valid:\n    %s", '\n    '.join(report))
    c = DispatcherConfig(cp)
    c.config_dir = config_dir
    return c


def get_device_config(name, config_dir):
    device_config = _get_config("devices/%s" % name, config_dir)
    cp = _get_config("device-defaults", config_dir, schema=DeviceSchema())
    _get_config(
        "device-types/%s" % device_config.get('__main__', 'device_type'),
        config_dir, cp=cp)
    _get_config("devices/%s" % name, config_dir, cp=cp)
    cp.set("__main__", "hostname", name)
    valid, report = cp.is_valid(report=True)
    if not valid:
        logging.warning("Config for %s is not valid:\n    %s", name, '\n    '.join(report))
    return DeviceConfig(cp)
