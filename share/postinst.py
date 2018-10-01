#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  postinst.py
#
#  Copyright 2018 Stevan Radaković <stevan.radakovic@linaro.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import os
import psycopg2
import pwd
import random
import shutil
import glob
import subprocess  # nosec - controlled inputs.
import sys

from lava_server.settings.config_file import ConfigFile


LAVA_SYS_MOUNTDIR = "/var/lib/lava-server/default/"
LAVA_SYS_HOME = "/var/lib/lava-server/home/"
LAVA_LOGS = "/var/log/lava-server/"
INSTANCE_CONF = "/etc/lava-server/instance.conf"
INSTANCE_TEMPLATE_CONF = "/usr/share/lava-server/instance.conf.template"
SECRET_KEY = "/etc/lava-server/secret_key.conf"
DISPATCHER_CONFIG = "/etc/lava-server/dispatcher-config/"
LAVA_DB_SERVER = "localhost"
# pylint: disable=line-too-long,missing-docstring


def psql_run(cmd_list, failure_msg):
    uid = pwd.getpwnam('postgres')[2]
    os.seteuid(uid)
    ret = run(cmd_list, failure_msg)
    uid = pwd.getpwnam('root')[2]
    os.seteuid(uid)
    return ret


def run(cmd_list, failure_msg):
    print(" ".join(cmd_list))
    try:
        ret = subprocess.check_call(cmd_list)  # nosec - internal.
    except subprocess.CalledProcessError:
        print(failure_msg)
        # all failures are fatal during setup
        sys.exit(1)
    return ret


def db_setup(config, pg_admin_username, pg_admin_password):

    # check postgres is not just installed but actually ready.
    run(
        ["pg_isready", "-d", config.LAVA_DB_NAME, "-p",
         "%s" % config.LAVA_DB_PORT, "-q"],
        "Failed to connect to postgres.")

    conn = psycopg2.connect("dbname='postgres' user='%s' host='%s' password='%s' connect_timeout=5" % (
        pg_admin_username,
        config.LAVA_DB_SERVER,
        pg_admin_password
    ))
    conn.autocommit = True
    # reuse the connection to manipulate DB.
    cursor = conn.cursor()

    try:
        cursor.execute("CREATE ROLE \"%s\" NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD '%s'" % (config.LAVA_DB_USER, config.LAVA_DB_PASSWORD))
    except psycopg2.ProgrammingError as exc:
        print(exc)

    cursor.execute("SELECT EXISTS(SELECT * FROM information_schema.tables WHERE table_name='%s')" % config.LAVA_DB_NAME)  # nosec - not accessible.
    db_existed_before = cursor.fetchone()[0]

    if not db_existed_before:
        try:
            cursor.execute("CREATE DATABASE \"%s\" LC_CTYPE 'C.UTF-8' ENCODING 'UTF-8' OWNER \"%s\" TEMPLATE template0" % (config.LAVA_DB_NAME, config.LAVA_DB_USER))
        except psycopg2.ProgrammingError as exc:
            print(exc)

    conn = psycopg2.connect("dbname='%s' user='%s' host='%s' password='%s' connect_timeout=5" % (
        config.LAVA_DB_NAME,
        pg_admin_username,
        config.LAVA_DB_SERVER,
        pg_admin_password
    ))
    conn.autocommit = True
    # reuse the connection to manipulate DB.
    cursor = conn.cursor()

    with contextlib.suppress(psycopg2.ProgrammingError):
        cursor.execute("CREATE ROLE devel NOSUPERUSER CREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD 'devel'")

    with contextlib.suppress(psycopg2.ProgrammingError):
        cursor.execute("""CREATE DATABASE OWNER devel devel""")

    if db_existed_before:
        run(['lava-server', 'manage', 'drop_materialized_views'],
            'materialized views')

    run(['lava-server', 'manage', 'migrate', '--noinput', '--fake-initial'],
        'migration')

    print("Refreshing all materialized views: lava-server manage refresh_queries --all")
    run(['lava-server', 'manage', 'refresh_queries', '--all'],
        'refresh_queries')

    cursor.execute("""SELECT * FROM pg_authid WHERE rolname='lavaserver'""")
    lava_user = cursor.fetchone()

    if not lava_user:
        run(['lava-server', 'manage', 'createsuperuser', '--noinput',
             '--username=%s' % config.LAVA_SYS_USER,
             '--email=%s@lava.invalid' % config.LAVA_SYS_USER],
            'create super user')


def configure():

    if os.path.exists(INSTANCE_CONF) and os.path.isfile(INSTANCE_CONF):
        config_path = INSTANCE_CONF
    else:
        config_path = INSTANCE_TEMPLATE_CONF

    config = ConfigFile.load(config_path)

    config.LAVA_DB_SERVER = LAVA_DB_SERVER

    if not hasattr(config, 'LAVA_SYS_USER'):
        config.LAVA_SYS_USER = "lavaserver"

    if not hasattr(config, 'LAVA_INSTANCE') or \
       config.LAVA_INSTANCE == '$LAVA_INSTANCE':
        config.LAVA_INSTANCE = "default"

    if not hasattr(config, 'LAVA_DB_NAME') or \
       config.LAVA_DB_NAME == '$LAVA_DB_NAME':
        config.LAVA_DB_NAME = "lavaserver"

    if not hasattr(config, 'LAVA_DB_USER') or \
       config.LAVA_DB_USER == '$LAVA_DB_USER':
        config.LAVA_DB_USER = "lavaserver"

    if not hasattr(config, 'LAVA_DB_PORT') or \
       config.LAVA_DB_PORT == '$LAVA_DB_PORT':
        config.LAVA_DB_PORT = 5432

    if not hasattr(config, 'LAVA_DB_PASSWORD') or \
       config.LAVA_DB_PASSWORD == '$LAVA_DB_PASSWORD':
        config.LAVA_DB_PASSWORD = "%012x" % random.getrandbits(48)

    ConfigFile.serialize(INSTANCE_CONF, config.__dict__)

    os.makedirs("%s/media/job-output/" % LAVA_SYS_MOUNTDIR, exist_ok=True)

    run(["adduser", "--quiet", "--system", "--group",
         "--home=%s" % LAVA_SYS_HOME, config.LAVA_SYS_USER, "--shell=/bin/sh"],
        'adduser')

    shutil.chown(LAVA_SYS_MOUNTDIR,
                 config.LAVA_SYS_USER,
                 config.LAVA_SYS_USER)
    shutil.chown("%s/media/" % LAVA_SYS_MOUNTDIR,
                 config.LAVA_SYS_USER,
                 config.LAVA_SYS_USER)
    shutil.chown("%s/media/job-output/" % LAVA_SYS_MOUNTDIR,
                 config.LAVA_SYS_USER,
                 config.LAVA_SYS_USER)

    # fixup bug from date based subdirectories - allowed to be missing.
    try:
        shutil.chown("%s/media/job-output/2017" % LAVA_SYS_MOUNTDIR,
                     config.LAVA_SYS_USER,
                     config.LAVA_SYS_USER)
    except FileNotFoundError:
        print("legacy directory is missing, skip..")

    # support changes in xml-rpc API for 2017.6
    shutil.chown(
        "/etc/lava-server/dispatcher.d/", config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    shutil.chown(
        DISPATCHER_CONFIG, config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    shutil.chown(
        "%s/devices/" % DISPATCHER_CONFIG, config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    shutil.chown(
        "%s/device-types/" % DISPATCHER_CONFIG, config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    # user may not have been removed but the directory has, after purge.
    if not os.path.isdir(LAVA_SYS_HOME):
        os.mkdir(LAVA_SYS_HOME)
        shutil.chown(LAVA_SYS_HOME, config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    # Fix permissions of /etc/lava-server/instance.conf
    shutil.chown(INSTANCE_CONF, config.LAVA_SYS_USER, config.LAVA_SYS_USER)
    os.chmod(INSTANCE_CONF, 0o640)

    os.makedirs(os.path.dirname(LAVA_LOGS), exist_ok=True)

    # Allow lavaserver to write to all the log files
    # setgid on LAVA_LOGS directory
    os.chmod(LAVA_LOGS, 0o2775)  # nosec - group permissive.

    # Allow users in the adm group to read all logs
    with open("%s/django.log" % LAVA_LOGS, 'w+') as logfile:
        logfile.write('')
    shutil.chown(LAVA_LOGS, user=config.LAVA_SYS_USER, group='adm')
    for file in glob.glob("%s/*" % LAVA_LOGS):
        if 'lava-scheduler.log' in file:
            # skip changes to old logs.
            continue
        shutil.chown(file, user=config.LAVA_SYS_USER, group='adm')
        # allow users in the adm group to run lava-server commands
        os.chmod(file, 0o0664)

    # tidy up old logrotate config to allow logrotate cron to complete.
    if os.path.exists('/etc/logrotate.d/lava-scheduler-log'):
        os.unlink('/etc/logrotate.d/lava-scheduler-log')

    # Allow lava user to write the secret key
    with open(SECRET_KEY, 'w+') as key:
        key.write('')
    shutil.chown(SECRET_KEY, config.LAVA_SYS_USER, config.LAVA_SYS_USER)
    os.chmod(SECRET_KEY, 0o640)

    # Allow lavaserver to write device dictionary files
    os.makedirs("%s/devices/" % DISPATCHER_CONFIG, exist_ok=True)
    shutil.chown(
        "%s/devices/" % DISPATCHER_CONFIG, config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    # Create temporary database role for db operations.
    pg_admin_username = "user_%012x" % random.getrandbits(48)
    pg_admin_password = "%012x" % random.getrandbits(48)

    result = psql_run(
        ["psql", "-c", "CREATE ROLE %s PASSWORD '%s' SUPERUSER CREATEDB CREATEROLE INHERIT LOGIN;" % (pg_admin_username, pg_admin_password)],
        "Failed to create temporary superuser role")

    if result != 0:
        print("Failed to create postgres superuser.")
        return

    try:
        db_setup(config, pg_admin_username, pg_admin_password)
    finally:
        # Removing temprorary user from postgres.
        result = psql_run(
            ["psql", "-c", "DROP ROLE %s ;" % pg_admin_username], "Failed to drop temporary superuser role.")
        if result != 0:
            print("Temporary user %s was not properly removed from postgres. Please do so manually." % pg_admin_username)


def main():
    configure()


if __name__ == '__main__':
    sys.exit(main())
