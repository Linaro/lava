#!/usr/bin/env python3
# Copyright (C) 2017-present Linaro Limited
#
# Author: Stevan Radaković <stevan.radakovic@linaro.org>
#         Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import contextlib
import grp
import importlib
import os
import pwd
import shutil
import subprocess  # nosec - controlled inputs.
import sys
import tempfile
from pathlib import Path

from django.core.management.utils import get_random_secret_key
from django.utils.crypto import get_random_string

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
SETTINGS_CONF = Path("/etc/lava-server/settings.conf")

GEN_SECRET_KEY = Path("/etc/lava-server/settings.d/00-secret-key.yaml")
GEN_DATABASE = Path("/etc/lava-server/settings.d/00-database.yaml")

LAVA_SYS_USER = "lavaserver"


def run(cmd_list, failure_msg, stdin=None):
    print(" ".join(cmd_list))
    try:
        ret = subprocess.check_call(cmd_list, stdin=stdin)  # nosec - internal.
    except subprocess.CalledProcessError:
        print(failure_msg)
        # all failures are fatal during setup
        sys.exit(1)
    return ret


def is_pg_available():
    # is the database ready?
    try:
        subprocess.check_call(["pg_isready"])
        return True
    except subprocess.CalledProcessError:
        print("Skipping database creation as PostgreSQL is not running")
        return False


def create_database(config):
    db = config["DATABASES"]["default"]["NAME"]
    password = config["DATABASES"]["default"]["PASSWORD"]
    user = config["DATABASES"]["default"]["USER"]
    devel_db = "devel"
    devel_password = "devel"
    devel_user = "devel"

    script = f"""
DO $$
BEGIN
    CREATE ROLE "{user}" NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD '{password}';
    EXCEPTION WHEN DUPLICATE_OBJECT THEN
    RAISE NOTICE 'not creating role {user} -- it already exists';
END
$$;

SELECT 'CREATE DATABASE "{db}" LC_COLLATE "C.UTF-8" LC_CTYPE "C.UTF-8" ENCODING "UTF-8" OWNER "{user}" TEMPLATE template0;'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{db}')\\gexec


DO $$
BEGIN
    CREATE ROLE "{devel_user}" NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT LOGIN ENCRYPTED PASSWORD '{devel_password}';
    EXCEPTION WHEN DUPLICATE_OBJECT THEN
    RAISE NOTICE 'not creating role {devel_user} -- it already exists';
END
$$;

SELECT 'CREATE DATABASE "{devel_db}" LC_COLLATE "C.UTF-8" LC_CTYPE "C.UTF-8" ENCODING "UTF-8" OWNER "{devel_user}" TEMPLATE template0;'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '{devel_db}')\\gexec
"""

    with tempfile.TemporaryFile() as f_tmp:
        f_tmp.write(script.encode("utf-8"))
        f_tmp.seek(0, 0)
        uid = pwd.getpwnam("postgres")[2]
        os.seteuid(uid)
        run(["psql", "-q"], "Creating databases and roles", stdin=f_tmp)
        uid = pwd.getpwnam("root")[2]
        os.seteuid(uid)


@contextlib.contextmanager
def using_account(user, group):
    euid = os.geteuid()
    egid = os.getegid()
    tuid = pwd.getpwnam(user).pw_uid
    tgid = grp.getgrnam(group).gr_gid
    try:
        os.setegid(tgid)
        os.seteuid(tuid)
        yield None
    finally:
        os.seteuid(euid)
        os.setegid(egid)


def update_database():
    with using_account(LAVA_SYS_USER, LAVA_SYS_USER):
        run(
            ["lava-server", "manage", "migrate", "--noinput", "--fake-initial"],
            "migration",
        )
        run(["lava-server", "manage", "drop_materialized_views"], "materialized views")
        run(["lava-server", "manage", "refresh_queries", "--all"], "refresh_queries")


def load_configuration():
    module = importlib.import_module("lava_server.settings.prod")
    # Reload the configuration as import_module will not reload the module
    module = importlib.reload(module)
    return {k: v for (k, v) in module.__dict__.items() if k.isupper()}


def fixup():
    print("* fix permissions:")
    directories = [
        # user may not have been removed but the directory has, after purge.
        (LAVA_SYS_HOME, True),
        (LAVA_SYS_MOUNTDIR, True),
        (LAVA_SYS_MOUNTDIR / "media", True),
        (LAVA_SYS_MOUNTDIR / "media" / "job-output", True),
        # support changes in xml-rpc API for 2017.6
        (DISPATCHER_CONFIG, False),
        (DISPATCHER_D, False),
    ]

    for item in directories:
        print(f"  - {item[0]}/")
        if item[1]:
            item[0].mkdir(mode=0o755, parents=True, exist_ok=True)
        shutil.chown(item[0], LAVA_SYS_USER, LAVA_SYS_USER)

    # fixup bug from date based subdirectories - allowed to be missing.
    with contextlib.suppress(FileNotFoundError):
        job_2017 = LAVA_SYS_MOUNTDIR / "media" / "job-output" / "2017"
        print(f"  - {job_2017}/")
        shutil.chown(job_2017, LAVA_SYS_USER, LAVA_SYS_USER)

    # Fix devices, device-types and health-checks owner/group
    for item in ["devices", "device-types", "health-checks"]:
        print(f"  - {DISPATCHER_CONFIG / item}/")
        shutil.chown(DISPATCHER_CONFIG / item, LAVA_SYS_USER, LAVA_SYS_USER)
        print(f"  - {DISPATCHER_CONFIG / item}/*")
        for filename in (DISPATCHER_CONFIG / item).glob("*"):
            shutil.chown(filename, LAVA_SYS_USER, LAVA_SYS_USER)

    # Drop files in DISPATCHER_CONFIG / "device-types" if the same exists in
    # DEVICE_TYPES
    print(f"* drop duplicated templates:")
    for item in sorted((DISPATCHER_CONFIG / "device-types").glob("*")):
        filename = item.name
        if (DEVICE_TYPES / filename).exists():
            data1 = (DISPATCHER_CONFIG / "device-types" / filename).read_text(
                encoding="utf-8"
            )
            data2 = (DEVICE_TYPES / filename).read_text(encoding="utf-8")
            if data1 == data2:
                print(f"  - {item}")
                item.unlink()

    print("* fix permissions:")
    # Fix permissions of /etc/lava-server/settings.conf
    with contextlib.suppress(FileNotFoundError):
        print(f"  - {SETTINGS_CONF}")
        shutil.chown(SETTINGS_CONF, LAVA_SYS_USER, LAVA_SYS_USER)
        SETTINGS_CONF.chmod(0o640)

    # Fix permissions of /etc/lava-server/instance.conf
    with contextlib.suppress(FileNotFoundError):
        print(f"  - {INSTANCE_CONF}")
        shutil.chown(INSTANCE_CONF, LAVA_SYS_USER, LAVA_SYS_USER)
        INSTANCE_CONF.chmod(0o640)

    # Allow lavaserver to write to all the log files
    # setgid on LAVA_LOGS directory
    print(f"  - {LAVA_LOGS}/")
    LAVA_LOGS.mkdir(mode=0o2775, parents=True, exist_ok=True)
    LAVA_LOGS.chmod(0o2775)  # nosec - group permissive.

    # Allow users in the adm group to read all logs
    (LAVA_LOGS / "django.log").write_text("", encoding="utf-8")
    print(f"  - {LAVA_LOGS}/*")
    for logfile in LAVA_LOGS.glob("*"):
        shutil.chown(logfile, LAVA_SYS_USER, "adm")
        # allow users in the adm group to run lava-server commands
        logfile.chmod(0o0664)

    # Fix secret_key.conf permission
    with contextlib.suppress(FileNotFoundError):
        print(f"  - {SECRET_KEY}")
        SECRET_KEY.chmod(0o640)
        shutil.chown(SECRET_KEY, LAVA_SYS_USER, LAVA_SYS_USER)


class YesNoAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, not option_string.startswith("--no"))


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
            options.db = is_pg_available()
        if options.fixup is None:
            options.fixup = True

    # Load configuration
    config = load_configuration()
    # Update the configuration if needed
    if options.config:
        print("Updating configuration:")
        if not config.get("SECRET_KEY"):
            print("* generate SECRET_KEY")
            GEN_SECRET_KEY.write_text(
                f"""# This file was generated by /usr/share/lava-server/postinst.py

# This key is used by Django to ensure the security of various cookies and
# one-time values. To learn more please visit:
# https://docs.djangoproject.com/en/3.2/ref/settings/#secret-key

# Note: DO NOT PUBLISH THIS FILE.

SECRET_KEY: "{get_random_secret_key()}"
""",
                encoding="utf-8",
            )
            GEN_SECRET_KEY.chmod(0o640)
            shutil.chown(GEN_SECRET_KEY, LAVA_SYS_USER, LAVA_SYS_USER)
        else:
            print("* generate SECRET_KEY [SKIP]")

        if options.db and not config.get("DATABASES"):
            print("* generate DATABASES")
            GEN_DATABASE.write_text(
                f"""# This file was generated by /usr/share/lava-server/postinst.py

# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

# Note: DO NOT PUBLISH THIS FILE.
DATABASES:
  default:
    ENGINE: "django.db.backends.postgresql"
    NAME: "lavaserver"
    USER: "lavaserver"
    PASSWORD: "{get_random_string()}"
    HOST: "localhost"
    PORT: 5432
""",
                encoding="utf-8",
            )
            GEN_DATABASE.chmod(0o640)
            shutil.chown(GEN_DATABASE, LAVA_SYS_USER, LAVA_SYS_USER)
        else:
            print("* generate DATABASES [SKIP]")

        # Reload the configuration
        config = load_configuration()

    # Run fixup scripts
    if options.fixup:
        print("Run fixups:")
        fixup()

    if options.db:
        print("Create database:")
        create_database(config)
        update_database()


if __name__ == "__main__":
    sys.exit(main())
