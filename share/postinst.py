#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2017-present Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#         Rémi Duraffort <remi.duraffort@linaro.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import contextlib
import os
import psycopg2
from pathlib import Path
import pwd
import random
import shutil
import subprocess  # nosec - controlled inputs.
import sys

from lava_server.settings.config_file import ConfigFile

# Constants
DEVICE_TYPES = Path("/usr/share/lava-server/device-types/")
DISPATCHER_CONFIG = Path("/etc/lava-server/dispatcher-config/")
DISPATCHER_D = Path("/etc/lava-server/dispatcher.d/")
INSTANCE_CONF = Path("/etc/lava-server/instance.conf")
INSTANCE_TEMPLATE_CONF = Path("/usr/share/lava-server/instance.conf.template")
LAVA_LOGS = Path("/var/log/lava-server/")
LAVA_SYS_HOME = Path("/var/lib/lava-server/home/")
LAVA_SYS_MOUNTDIR = Path("/var/lib/lava-server/default/")
SECRET_KEY = Path("/etc/lava-server/secret_key.conf")


def psql_run(cmd_list, failure_msg):
    uid = pwd.getpwnam("postgres")[2]
    os.seteuid(uid)
    ret = run(cmd_list, failure_msg)
    uid = pwd.getpwnam("root")[2]
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
        [
            "pg_isready",
            "--host=%s" % config.LAVA_DB_SERVER,
            "--port=%s" % config.LAVA_DB_PORT,
            "--quiet",
        ],
        "Failed to connect to postgres.",
    )

    conn = psycopg2.connect(
        "dbname='postgres' user='%s' host='%s' password='%s' connect_timeout=5"
        % (pg_admin_username, config.LAVA_DB_SERVER, pg_admin_password)
    )
    conn.autocommit = True
    # reuse the connection to manipulate DB.
    cursor = conn.cursor()

    try:
        cursor.execute(
            "CREATE ROLE \"%s\" NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD '%s'"
            % (config.LAVA_DB_USER, config.LAVA_DB_PASSWORD)
        )
    except psycopg2.ProgrammingError as exc:
        print(exc)

    cursor.execute(
        "SELECT EXISTS(SELECT * FROM information_schema.tables WHERE table_name='%s')"
        % config.LAVA_DB_NAME
    )  # nosec - not accessible.
    db_existed_before = cursor.fetchone()[0]

    if not db_existed_before:
        try:
            cursor.execute(
                "CREATE DATABASE \"%s\" LC_CTYPE 'C.UTF-8' ENCODING 'UTF-8' OWNER \"%s\" TEMPLATE template0"
                % (config.LAVA_DB_NAME, config.LAVA_DB_USER)
            )
        except psycopg2.ProgrammingError as exc:
            print(exc)

    conn = psycopg2.connect(
        "dbname='%s' user='%s' host='%s' password='%s' connect_timeout=5"
        % (
            config.LAVA_DB_NAME,
            pg_admin_username,
            config.LAVA_DB_SERVER,
            pg_admin_password,
        )
    )
    conn.autocommit = True
    # reuse the connection to manipulate DB.
    cursor = conn.cursor()

    with contextlib.suppress(psycopg2.ProgrammingError):
        cursor.execute(
            "CREATE ROLE devel NOSUPERUSER CREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD 'devel'"
        )

    with contextlib.suppress(psycopg2.ProgrammingError):
        cursor.execute("""CREATE DATABASE OWNER devel devel""")

    if db_existed_before:
        run(["lava-server", "manage", "drop_materialized_views"], "materialized views")

    run(
        ["lava-server", "manage", "migrate", "--noinput", "--fake-initial"], "migration"
    )

    print("Refreshing all materialized views: lava-server manage refresh_queries --all")
    run(["lava-server", "manage", "refresh_queries", "--all"], "refresh_queries")

    cursor.execute("""SELECT * FROM pg_authid WHERE rolname='lavaserver'""")
    lava_user = cursor.fetchone()

    if not lava_user:
        run(
            [
                "lava-server",
                "manage",
                "createsuperuser",
                "--noinput",
                "--username=%s" % config.LAVA_SYS_USER,
                "--email=%s@lava.invalid" % config.LAVA_SYS_USER,
            ],
            "create super user",
        )


def database(config):
    # Create temporary database role for db operations.
    pg_admin_username = "user_%012x" % random.getrandbits(48)
    pg_admin_password = "%012x" % random.getrandbits(48)

    result = psql_run(
        [
            "psql",
            "-c",
            "CREATE ROLE %s PASSWORD '%s' SUPERUSER CREATEDB CREATEROLE INHERIT LOGIN;"
            % (pg_admin_username, pg_admin_password),
        ],
        "Failed to create temporary superuser role",
    )

    if result != 0:
        print("Failed to create postgres superuser.")
        return

    try:
        db_setup(config, pg_admin_username, pg_admin_password)
    finally:
        # Removing temprorary user from postgres.
        result = psql_run(
            ["psql", "-c", "DROP ROLE %s ;" % pg_admin_username],
            "Failed to drop temporary superuser role.",
        )
        if result != 0:
            print(
                "Temporary user %s was not properly removed from postgres. Please do so manually."
                % pg_admin_username
            )


def load_configuration():
    if INSTANCE_CONF.exists():
        config_path = INSTANCE_CONF
    else:
        config_path = INSTANCE_TEMPLATE_CONF

    config = ConfigFile.load(config_path)

    if not hasattr(config, "LAVA_DB_SERVER"):
        config.LAVA_DB_SERVER = "localhost"

    if not hasattr(config, "LAVA_SYS_USER"):
        config.LAVA_SYS_USER = "lavaserver"

    if not hasattr(config, "LAVA_INSTANCE") or config.LAVA_INSTANCE == "$LAVA_INSTANCE":
        config.LAVA_INSTANCE = "default"

    if not hasattr(config, "LAVA_DB_NAME") or config.LAVA_DB_NAME == "$LAVA_DB_NAME":
        config.LAVA_DB_NAME = "lavaserver"

    if not hasattr(config, "LAVA_DB_USER") or config.LAVA_DB_USER == "$LAVA_DB_USER":
        config.LAVA_DB_USER = "lavaserver"

    if not hasattr(config, "LAVA_DB_PORT") or config.LAVA_DB_PORT == "$LAVA_DB_PORT":
        config.LAVA_DB_PORT = 5432

    if (
        not hasattr(config, "LAVA_DB_PASSWORD")
        or config.LAVA_DB_PASSWORD == "$LAVA_DB_PASSWORD"
    ):
        config.LAVA_DB_PASSWORD = "%012x" % random.getrandbits(48)

    return config


def fixup(config):
    directories = [
        # user may not have been removed but the directory has, after purge.
        (LAVA_SYS_HOME, True),
        (LAVA_SYS_MOUNTDIR, True),
        (LAVA_SYS_MOUNTDIR / "media", True),
        (LAVA_SYS_MOUNTDIR / "media" / "job-output", True),
        # support changes in xml-rpc API for 2017.6
        (DISPATCHER_CONFIG, False),
        (DISPATCHER_CONFIG / "devices", False),
        (DISPATCHER_CONFIG / "device-types", False),
        (DISPATCHER_CONFIG / "health-checks", False),
        (DISPATCHER_D, False),
    ]

    for item in directories:
        if item[1]:
            item[0].mkdir(mode=0o755, parents=True, exist_ok=True)
        shutil.chown(item[0], config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    # fixup bug from date based subdirectories - allowed to be missing.
    with contextlib.suppress(FileNotFoundError):
        shutil.chown(
            LAVA_SYS_MOUNTDIR / "media" / "job-output" / "2017",
            config.LAVA_SYS_USER,
            config.LAVA_SYS_USER,
        )

    # Fix devices, device-types and health-checks ownes/group
    for item in ["devices", "device-types", "health-checks"]:
        for filename in (DISPATCHER_CONFIG / item).glob("*"):
            shutil.chown(filename, config.LAVA_SYS_USER, config.LAVA_SYS_USER)

    # Drop files in DISPATCHER_CONFIG / "device-types" if the same exists in
    # DEVICE_TYPES
    for item in (DISPATCHER_CONFIG / "device-types").glob("*"):
        filename = item.name
        if (DEVICE_TYPES / filename).exists():
            data1 = (DISPATCHER_CONFIG / "device-types" / filename).read_text(
                encoding="utf-8"
            )
            data2 = (DEVICE_TYPES / filename).read_text(encoding="utf-8")
            if data1 == data2:
                print(f"Removing duplicated template {item}")
                item.unlink()

    # Fix permissions of /etc/lava-server/instance.conf
    with contextlib.suppress(FileNotFoundError):
        shutil.chown(INSTANCE_CONF, config.LAVA_SYS_USER, config.LAVA_SYS_USER)
        INSTANCE_CONF.chmod(0o640)

    # Allow lavaserver to write to all the log files
    # setgid on LAVA_LOGS directory
    LAVA_LOGS.mkdir(mode=0o2775, parents=True, exist_ok=True)
    LAVA_LOGS.chmod(0o2775)  # nosec - group permissive.

    # Allow users in the adm group to read all logs
    (LAVA_LOGS / "django.log").write_text("", encoding="utf-8")
    for f in LAVA_LOGS.glob("*"):
        if "lava-scheduler.log" in str(f):
            # skip changes to old logs.
            continue
        shutil.chown(f, config.LAVA_SYS_USER, "adm")
        # allow users in the adm group to run lava-server commands
        f.chmod(0o0664)

    # Allow lava user to write the secret key
    SECRET_KEY.write_text("", encoding="utf-8")
    SECRET_KEY.chmod(0o640)
    shutil.chown(SECRET_KEY, config.LAVA_SYS_USER, config.LAVA_SYS_USER)


class YesNoAction(argparse.Action):
    def __call__(self, parser, ns, values, option):
        setattr(ns, self.dest, not option.startswith("--no"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        "--no-config",
        dest="config",
        action=YesNoAction,
        default=None,
        nargs=0,
        help="Update the configuration",
    )
    parser.add_argument(
        "--db",
        "--no-db",
        dest="db",
        action=YesNoAction,
        default=None,
        nargs=0,
        help="Setup the database",
    )
    parser.add_argument(
        "--fixup",
        "--no-fixup",
        dest="fixup",
        action=YesNoAction,
        default=None,
        nargs=0,
        help="Fixup issues with previous versions",
    )

    # Parse command line
    options = parser.parse_args()
    if not any([options.config, options.db, options.fixup]):
        if options.config is None:
            options.config = True
        if options.db is None:
            options.db = True
        if options.fixup is None:
            options.fixup = True

    # Load configuration
    config = load_configuration()

    # Update the configuration if needed
    if options.config:
        # Only dump if the file does not exists
        if not INSTANCE_CONF.exists():
            ConfigFile.serialize(str(INSTANCE_CONF), config.__dict__)
            shutil.chown(INSTANCE_CONF, config.LAVA_SYS_USER, config.LAVA_SYS_USER)
            INSTANCE_CONF.chmod(0o640)

    # Run fixup scripts
    if options.fixup:
        fixup(config)

    if options.db:
        database(config)


if __name__ == "__main__":
    sys.exit(main())
