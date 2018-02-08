#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  download-test-suites-api.py
#
#  Copyright 2018 Linaro Limited
#  Author: Stevan Radakovic <stevan.radakovic@linaro.org>
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
import requests
import yaml


def main():
    parser = argparse.ArgumentParser(description='LAVA test suite download showcase')
    parser.add_argument(
        '--instance',
        type=str,
        required=True,
        help='XMLRPC endpoint')
    parser.add_argument(
        '--username',
        default=None,
        type=str,
        help='Username used for authentication')
    parser.add_argument(
        '--token',
        default=None,
        type=str,
        help='Token used for authentication')
    parser.add_argument(
        '--job-id',
        type=str,
        required=True,
        help='Job ID')
    parser.add_argument(
        '--https',
        action='store_true',
        help='Use https instead of http')
    parser.add_argument(
        'testsuites',
        nargs='+',
        help='Specify list of test suite names which should be downloaded')
    args = parser.parse_args()

    protocol = 'https' if args.https else 'http'

    job_results_url = '%s://%s/results/%s' % (protocol,
                                              args.instance,
                                              args.job_id)
    summary_response = requests.get(
        '%s/yaml_summary' % (job_results_url),
        params={'user': args.username, 'token': args.token})

    for test_suite in yaml.load(summary_response.content):
        if test_suite['name'] in args.testsuites:
            print("Test case list for suite '%s':" % test_suite["name"])
            suite_response = requests.get(
                '%s/%s/yaml' % (job_results_url, test_suite['name']),
                params={'user': args.username, 'token': args.token})

            for test_case in yaml.load(suite_response.content):
                print("- %s" % test_case["name"])


if __name__ == '__main__':
    main()
