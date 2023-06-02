#!/usr/bin/python3
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import contextlib
import itertools
import os
import shlex
import subprocess
import sys
import time

import requests

#############
# Constants #
#############
GITLAB_API = "https://git.lavasoftware.org/api/v4/projects/2"
REGISTRY = "hub.lavasoftware.org/lava/lava"
COLORS = {
    "blue": "\x1b[1;34;40m",
    "purple": "\x1b[1;35;40m",
    "red": "\x1b[1;31;40m",
    "white": "\x1b[1;37;40m",
    "yellow": "\x1b[1;33;40m",
    "reset": "\x1b[0m",
}


###########
# Helpers #
###########
def run(cmd, options, env=None, shell=False):
    print(
        "%s[%02d] $ %s%s%s"
        % (COLORS["blue"], options.count, COLORS["white"], cmd, COLORS["reset"])
    )
    if options.steps and options.skip < options.count:
        try:
            input()
        except EOFError:
            options.steps = False
    ret = 0
    if options.skip >= options.count:
        print("-> skip")
    elif not options.dry_run:
        if env is not None:
            env = {**os.environ, **env}
        if shell:
            ret = subprocess.call(cmd, env=env, shell=True)
        else:
            ret = subprocess.call(shlex.split(cmd), env=env)
    options.count += 1
    print("")
    if ret != 0:
        raise Exception("Unable to run '%s', returned %d" % (cmd, ret))


def wait_pipeline(options, commit):
    # Wait for the pipeline to finish
    while True:
        with contextlib.suppress(AttributeError):
            ret = requests.get(GITLAB_API + "/repository/commits/" + commit)
            status = ret.json().get("last_pipeline", {}).get("status", "")
            if status == "success":
                break
            elif status == "failed":
                raise Exception("The pipeline failed")
            elif status == "canceled":
                raise Exception("The pipeline was canceled")
            elif status == "skipped":
                raise Exception("The pipeline was skipped")
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(10)


############
# Handlers #
############
def handle_prepare(options):
    # Generate the debian changelog
    run(
        'gbp dch --git-author --new-version="%s-1" --id-length=9 --release --commit --commit-msg="LAVA Software %s release" debian'
        % (options.version, options.version),
        options,
    )
    # Update the version number
    run("echo '%s' > lava_common/VERSION" % options.version, options, shell=True)
    run("git commit --amend --reuse-message HEAD lava_common/VERSION", options)
    # Create the git tag
    run(
        'git tag --annotate --message="LAVA Software %s release" --sign -u release@lavasoftware.org %s'
        % (options.version, options.version),
        options,
    )


def handle_build(options):
    run(".gitlab-ci/build/debian/11.sh", options)
    run(".gitlab-ci/build/docker.sh dispatcher", options)
    run(".gitlab-ci/build/docker.sh server", options)
    run(".gitlab-ci/build/doc.sh", options)


def handle_test(options):
    run(".gitlab-ci/analyze/black.sh", options)
    run(".gitlab-ci/analyze/schemas.sh", options)
    run(".gitlab-ci/analyze/pylint.sh", options)
    run(".gitlab-ci/test/dispatcher-debian-11.sh", options)
    run(".gitlab-ci/test/server-debian-11.sh", options)


def handle_push(options):
    # Push the commit and wait for the CI
    run("git push origin master", options)
    commit = (
        subprocess.check_output(["git", "rev-parse", "origin/master"])
        .decode("utf-8")
        .rstrip("\n")
    )

    print("%s# wait for CI%s" % (COLORS["purple"], COLORS["reset"]))
    if not options.dry_run and not options.skip >= options.count:
        wait_pipeline(options, commit)
    print("done\n")

    # The CI was a success so we can push the tag
    run("git push --tags origin master", options)


def handle_publish(options):
    # Check that the CI was a success
    print("%s# wait for CI%s" % (COLORS["purple"], COLORS["reset"]))
    if not options.dry_run and not options.skip >= options.count:
        commit = (
            subprocess.check_output(["git", "rev-parse", options.version])
            .decode("utf-8")
            .rstrip("\n")
        )
        wait_pipeline(options, commit)
    print("done\n")

    connection_string = "git.lavasoftware.org"
    if options.lavasoftware_username:
        connection_string = "%s@%s" % (
            options.lavasoftware_username,
            connection_string,
        )

    print("%s# publish the new repository%s" % (COLORS["purple"], COLORS["reset"]))
    run(
        "ssh -t %s 'cd /home/gitlab-runner/repository && sudo ln -snf current-release release'"
        % connection_string,
        options,
    )

    # Login to the docker service.
    run("docker login", options)

    # Pull/Push the docker images
    for name, arch in itertools.product(["dispatcher", "server"], ["aarch64", "amd64"]):
        print(
            "%s# push docker images for (%s, %s)%s"
            % (COLORS["purple"], name, arch, COLORS["reset"])
        )
        run(
            "docker pull %s/%s/lava-%s:%s" % (REGISTRY, arch, name, options.version),
            options,
        )
        run(
            "docker tag %s/%s/lava-%s:%s lavasoftware/%s-lava-%s:%s"
            % (REGISTRY, arch, name, options.version, arch, name, options.version),
            options,
        )
        run(
            "docker push lavasoftware/%s-lava-%s:%s" % (arch, name, options.version),
            options,
        )
        run(
            "docker tag %s/%s/lava-%s:%s lavasoftware/%s-lava-%s:latest"
            % (REGISTRY, arch, name, options.version, arch, name),
            options,
        )
        run("docker push lavasoftware/%s-lava-%s:latest" % (arch, name), options)

    print("%s# push docker manifests%s" % (COLORS["purple"], COLORS["reset"]))
    for name in ["dispatcher", "server"]:
        run(
            "docker manifest create lavasoftware/lava-%s:%s lavasoftware/aarch64-lava-%s:%s lavasoftware/amd64-lava-%s:%s"
            % (name, options.version, name, options.version, name, options.version),
            options,
            env={"DOCKER_CLI_EXPERIMENTAL": "enabled"},
        )
        run(
            "docker manifest push --purge lavasoftware/lava-%s:%s"
            % (name, options.version),
            options,
            env={"DOCKER_CLI_EXPERIMENTAL": "enabled"},
        )
        run(
            "docker manifest create lavasoftware/lava-%s:latest lavasoftware/aarch64-lava-%s:latest lavasoftware/amd64-lava-%s:latest"
            % (name, name, name),
            options,
            env={"DOCKER_CLI_EXPERIMENTAL": "enabled"},
        )
        run(
            "docker manifest push --purge lavasoftware/lava-%s:latest" % (name),
            options,
            env={"DOCKER_CLI_EXPERIMENTAL": "enabled"},
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--actions",
        default="prepare,build,test,push,publish",
        help="comma separated list of actions",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=False,
        help="do not run any command",
    )
    parser.add_argument(
        "--steps", action="store_true", default=False, help="Run step by step"
    )
    parser.add_argument("--skip", type=int, default=0, help="Skip some steps")
    parser.add_argument("version", type=str, help="new version")
    parser.add_argument(
        "--lavasoftware-username",
        default=None,
        help="username for lavasoftware.org SSH login",
    )

    # Parse the command line
    options = parser.parse_args()

    handlers = {
        "prepare": handle_prepare,
        "build": handle_build,
        "test": handle_test,
        "push": handle_push,
        "publish": handle_publish,
    }

    first = True
    options.count = 1
    for action in options.actions.split(","):
        if action in handlers:
            if not first:
                print("")
            print("%s%s%s" % (COLORS["yellow"], action.capitalize(), COLORS["reset"]))
            print("%s%s%s" % (COLORS["yellow"], "-" * len(action), COLORS["reset"]))
            try:
                handlers[action](options)
            except Exception as exc:
                print("%sexception: %s%s" % (COLORS["red"], str(exc), COLORS["reset"]))
                raise
                return 1
        else:
            raise NotImplementedError("Action '%s' does not exists" % action)
        first = False


if __name__ == "__main__":
    sys.exit(main())
