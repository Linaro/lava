#!/usr/bin/python3
#
# Copyright (C) 2019 Linaro Limited
#
# Author: Rémi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import argparse
import re
import sys

import requests

PROJECT = {"lava": 47541627}

REPOSITORIES = {
    "aarch64/lava-dispatcher": 4378164,
    "aarch64/lava-dispatcher-base": 4378155,
    "aarch64/lava-server": 4378163,
    "aarch64/lava-server-base": 4378158,
    "amd64/lava-dispatcher": 4378168,
    "amd64/lava-dispatcher-base": 4378160,
    "amd64/lava-server": 4378169,
    "amd64/lava-server-base": 4378166,
}


def list_tags(options):
    headers = {"PRIVATE-TOKEN": options.token}
    url = "%s/projects/%d/registry/repositories/%d/tags" % (
        options.url,
        options.project,
        options.repository,
    )
    ret = requests.get(url, headers=headers, timeout=60.0)
    assert ret.status_code == 200
    total_pages = int(ret.headers["X-Total-Pages"])

    tags = []
    for index in range(1, total_pages + 1):
        ret = requests.get("%s?page=%d" % (url, index), headers=headers, timeout=60.0)
        for tag in ret.json():
            tags.append(tag["name"])
    return tags


def filter_tags(tags, pattern):
    pattern = re.compile(pattern)
    return [tag for tag in tags if pattern.match(tag)]


def delete_tags(options, tags):
    headers = {"PRIVATE-TOKEN": options.token}
    url = "%s/projects/%d/registry/repositories/%d/tags/" % (
        options.url,
        options.project,
        options.repository,
    )
    for tag in tags:
        print("* %s" % tag)
        ret = requests.delete("%s/%s/" % (url, tag), headers=headers, timeout=60.0)
        print("=> %d" % ret.status_code)


def main():
    # Build the parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--filter", type=str, default=None, help="Pattern to filter tags"
    )
    parser.add_argument(
        "--delete", action="store_true", default=False, help="Delete tags"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="https://gitlab.com/api/v4/",
        help="base url",
    )
    parser.add_argument("--token", type=str, default=None, help="private gitlab token")
    parser.add_argument("project", type=str, default=47541627, help="project id 'lava'")
    parser.add_argument(
        "repository",
        type=str,
        help="repository id or (aarch64|amd64)/lava-(dispatcher|server)",
    )

    # parse the command line
    options = parser.parse_args()

    # Lookup the project name if needed
    try:
        options.project = int(PROJECT.get(options.project, options.project))
    except ValueError:
        print("'%s' should be an int or a known project" % options.project)
        return 1
    try:
        options.repository = int(
            REPOSITORIES.get(options.repository, options.repository)
        )
    except ValueError:
        print("'%s' should be an int or a known repository" % options.repository)
        return 1

    # List the tags
    tags = list_tags(options)
    if options.filter is not None:
        tags = filter_tags(tags, options.filter)
    if options.delete:
        delete_tags(options, tags)
    else:
        for tag in tags:
            print("* %s" % tag)


if __name__ == "__main__":
    sys.exit(main())
