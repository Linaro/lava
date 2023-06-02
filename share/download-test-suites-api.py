#!/usr/bin/env python3
#
#  download-test-suites-api.py
#
#  Copyright 2018 Linaro Limited
#  Author: Stevan Radakovic <stevan.radakovic@linaro.org>
#
# SPDX-License-Identifier: GPL-3.0-or-later


import argparse

import requests
import yaml


def main():
    parser = argparse.ArgumentParser(description="LAVA test suite download showcase")
    parser.add_argument("--instance", type=str, required=True, help="XMLRPC endpoint")
    parser.add_argument(
        "--username", default=None, type=str, help="Username used for authentication"
    )
    parser.add_argument(
        "--token", default=None, type=str, help="Token used for authentication"
    )
    parser.add_argument("--job-id", type=str, required=True, help="Job ID")
    parser.add_argument(
        "--https", action="store_true", help="Use https instead of http"
    )
    parser.add_argument(
        "testsuites",
        nargs="+",
        help="Specify list of test suite names which should be downloaded",
    )
    args = parser.parse_args()

    protocol = "https" if args.https else "http"

    job_results_url = "%s://%s/results/%s" % (protocol, args.instance, args.job_id)
    summary_response = requests.get(
        "%s/yaml_summary" % (job_results_url),
        params={"user": args.username, "token": args.token},
    )

    for test_suite in yaml.safe_load(summary_response.content):
        if test_suite["name"] in args.testsuites:
            print("Test case list for suite '%s':" % test_suite["name"])
            suite_response = requests.get(
                "%s/%s/yaml" % (job_results_url, test_suite["name"]),
                params={"user": args.username, "token": args.token},
            )

            for test_case in yaml.safe_load(suite_response.content):
                print("- %s" % test_case["name"])


if __name__ == "__main__":
    main()
