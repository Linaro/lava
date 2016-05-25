#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  release-queue.py
#
#  Copyright 2014 Linaro Limited
#  Author: Neil Williams <neil.williams@linaro.org>
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

import argparse
import re
import subprocess
import time


change_id_pattern = re.compile("\s+Change-Id: (\w+)")
commit_pattern = re.compile("commit (.+)")
author_pattern = re.compile("author ([^>]+>) (\w+) ((\+|-)\w\w\w\w)")


class Commit(object):
    def __init__(self, commit_id, change_id):
        self.commit_id = commit_id
        self.change_id = change_id

        self.obj = subprocess.check_output(['git', 'cat-file', '-p', self.commit_id]).decode('utf-8')
        break_next_time = False

        for line in self.obj.split('\n'):
            if break_next_time:
                self.message = line
                break

            if line == '':
                break_next_time = True
            elif line[0:6] == 'author':
                m = author_pattern.match(line)
                if m:
                    self.author = m.group(1)
                    self.time = m.group(2)

    def get_time(self):
        t = time.gmtime(float(self.time))
        return "%02d/%02d/%d %02d:%02d" % (t.tm_mon, t.tm_mday, t.tm_year, t.tm_hour, t.tm_min)

    def render(self):
        return "%s (%s %s): %s" % (self.get_time(), self.commit_id, self.change_id, self.message)


def get_change_ids(branch):
    results = []

    subprocess.check_output(["git", "checkout", branch], stderr=subprocess.STDOUT)
    lines = subprocess.check_output(["git", "log"]).decode('utf-8')
    for line in lines.split('\n'):
        if "Change-Id" in line:
            m = change_id_pattern.match(line)
            results.append(m.group(1))
    return results


def main():
    # Add the argument parse
    parser = argparse.ArgumentParser(description='Show the missing commits in release branch')
    parser.add_argument('-c', '--changelog', dest='changelog', action='store_true',
                        default=False, help='Print the changelog')
    parser.add_argument('-b', '--branch', dest='branch',
                        default='release', help='branch to compare with base branch')
    parser.add_argument('-s', '--staging', dest='staging', action='store_true',
                        default=False, help='compare branch against staging')
    args = parser.parse_args()

    # Check the current working directory
    try:
        subprocess.check_call(["git", "rev-parse"])
    except subprocess.CalledProcessError:
        print("Ensure this script is run from the git working copy.")
        return 1

    master_branch = 'staging' if args.staging else 'master'
    # Get all change ids between master_branch and release
    master = get_change_ids(master_branch)
    release = get_change_ids(args.branch)

    diff = list(set(master) - set(release))
    diff.sort()

    # Go back to master
    subprocess.check_output(["git", "checkout", master_branch], stderr=subprocess.STDOUT)
    lines = subprocess.check_output(["git", "log"]).decode('utf-8')

    # List the missing commits
    current_hash = ''
    commits = []
    for change in diff:
        for line in lines.split('\n'):
            # Get the commit hash
            if "commit " in line:
                m = commit_pattern.match(line)
                if m:
                    current_hash = m.group(1)
            # Match the Change-id
            if "Change-Id" in line:
                m = change_id_pattern.match(line)
                if change == m.group(1):
                    commits.append(Commit(current_hash, change))
                    break

    commits.sort(key=lambda x: x.time, reverse=True)
    if args.changelog:
        for c in commits:
            print(c.message)
    else:
        for c in commits:
            print(c.render())

    return 0

if __name__ == '__main__':
    main()
