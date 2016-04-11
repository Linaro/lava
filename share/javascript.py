#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  javascript.py
#
#  Copyright 2015 Neil Williams <codehelp@debian.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#

import os
import sys
import yaml
import argparse
import subprocess

# pylint: disable=too-many-branches

# Adds a dependency on python-yaml when used during a build.


def check_os(os_name, data):
    """
    Isolate just the data for the requested OS
    Only debian supported so far.
    """
    for key, list_data in data.items():
        if key == os_name:
            yield list_data


def handle_embedded(os_name, data, dirname, simulate=False):
    """
    Remove the packaged duplicate
    Create a symlink from the external package to the old name
    $(RM) $(CURDIR)/$(JS_DIR)/lava_server/lava-server/js/jquery-1.11.0.min.js
    """
    python_dir = None
    dependencies = {}
    os_check = check_os(os_name, data)
    for os_data in os_check.next():
        for dkey, value in os_data.items():
            if dkey == 'python_dir':
                python_dir = value
                if python_dir.startswith('/'):
                    python_dir = str(python_dir[1:])
            elif dkey == 'package':
                package = os_data
                print 'Linking files from "%s" into "%s"' % (
                    package['package'],
                    package['lava_directory']
                )
                if 'version' in package:
                    dependencies[package['package']] = "(>= %s)" % package['version']
                else:
                    dependencies[package['package']] = None
            elif dkey == 'replacements':
                package = os_data
                for ours, external in package['replacements'].items():
                    ext_path = os.path.join(package['directory'], external)
                    our_path = os.path.join(
                        dirname, python_dir, package['lava_directory'], ours)
                    if not os.path.exists(ext_path):
                        raise RuntimeError("missing %s" % ext_path)
                    if not simulate:
                        if not os.path.exists(our_path):
                            raise RuntimeError("missing %s" % our_path)
                        os.unlink(our_path)
                        os.symlink(ext_path, our_path)
                    else:
                        print "rm %s" % our_path
                        print "ln -s %s %s" % (ext_path, our_path)
    return dependencies


def uglify(os_name, data, dirname, remove=False, simulate=False):
    """
    """
    python_dir = None
    os_check = check_os(os_name, data)
    for os_data in os_check.next():
        for dkey, value in os_data.items():
            if dkey == 'python_dir':
                python_dir = value
                if python_dir.startswith('/'):
                    python_dir = str(python_dir[1:])
            elif dkey == 'uglify':
                package = os_data
                lava_dir = package['lava_directory']
                dest_dir = package['destination']

                for file_name, dest_name in package['files'].items():

                    orig_path = os.path.join(lava_dir, file_name)
                    install_path = os.path.join(dirname, python_dir, lava_dir,
                                                file_name)
                    dest_path = os.path.join(dirname, python_dir,
                                             dest_dir, dest_name)

                    if not simulate:
                        try:
                            subprocess.check_call(
                                ['uglifyjs', orig_path, '-o',
                                 dest_path, '-c', '-m'],
                                stderr=open(os.devnull, 'wb'))
                        except Exception as e:
                            print e

                        if remove:
                            if not os.path.exists(install_path):
                                print "WARNING: JS file %s does not exist" % (
                                    install_path)
                                continue
                            os.unlink(install_path)
                    else:
                        print "uglifyjs %s -o %s -c -m" % (orig_path,
                                                           dest_path)

    return None


def main():
    """
    Parse options and load the supporting YAML file.
    Where debian is used, debian === debian-based
    """
    parser = argparse.ArgumentParser(
        description='Handle embedded javascript')
    parser.add_argument(
        '-f', '--filename', required=True,
        help='YAML file describing embedded javascript')
    parser.add_argument(
        '-r', '--remove',
        action='store_true', help='Remove original js files from .deb')
    parser.add_argument(
        '-s', '--simulate',
        action='store_true', help='Only echo the commands')

    args = parser.parse_args()
    data = yaml.load(open(args.filename, 'r'))
    # only have data for debian-based packages so far.
    dependencies = handle_embedded('debian', data, os.getcwd(), args.simulate)
    dep_list = []
    for package, constraint in dependencies.items():
        if constraint:
            dep_list.append("%s %s" % (package, constraint))
        else:
            dep_list.append(package)
    if args.simulate:
        # only useful for Debian-based
        print ""
        print "Build-Depends:", ", ".join(sorted(dep_list))
        print "Depends:", ", ".join(sorted(dep_list))

    uglify('debian', data, os.getcwd(), args.remove, args.simulate)
    return 0

if __name__ == '__main__':
    sys.exit(main())
