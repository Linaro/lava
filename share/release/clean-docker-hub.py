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

PROJECT = {"lava": 2}

REPOSITORIES = {
    "aarch64/lava-dispatcher": 74,
    "aarch64/lava-dispatcher-base": 149,
    "aarch64/lava-server": 75,
    "aarch64/lava-server-base": 152,
    "amd64/lava-dispatcher": 72,
    "amd64/lava-dispatcher-base": 150,
    "amd64/lava-server": 73,
    "amd64/lava-server-base": 151,
}


def list_tags(options):
    headers = {"PRIVATE-TOKEN": options.token}
    url = "%s/projects/%d/registry/repositories/%d/tags" % (
        options.url,
        options.project,
        options.repository,
    )
    ret = requests.get(url, headers=headers)
    assert ret.status_code == 200
    total_pages = int(ret.headers["X-Total-Pages"])

    tags = []
    for index in range(1, total_pages + 1):
        ret = requests.get("%s?page=%d" % (url, index), headers=headers)
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
        ret = requests.delete("%s/%s/" % (url, tag), headers=headers)
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
        default="https://git.lavasoftware.org/api/v4/",
        help="base url",
    )
    parser.add_argument("--token", type=str, default=None, help="private gitlab token")
    parser.add_argument("project", type=str, default=2, help="project id 'lava'")
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
