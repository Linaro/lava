#!/usr/bin/env python3
#
#  incomplete-results.py
#
#  Copyright 2017 Neil Williams <codehelp@debian.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
#
#


import sys
import xmlrpc.client

import yaml

# configuration
USER = "neil.williams"
TOKEN = ""
QUERY = "testing-myjobs"
QUERY_USER = "neil.williams"
HOSTNAME = "localhost"
# end configuration

SUBMITTED = 0
RUNNING = 1
COMPLETE = 2
INCOMPLETE = 3
CANCELED = 4
CANCELING = 5

STATUS_CHOICES = (
    (SUBMITTED, "Submitted"),
    (RUNNING, "Running"),
    (COMPLETE, "Complete"),
    (INCOMPLETE, "Incomplete"),
    (CANCELED, "Canceled"),
    (CANCELING, "Canceling"),
)


# main_function
def main(args):
    # change https to http when testing with localhost
    connection = xmlrpc.client.ServerProxy(
        "https://%s:%s@%s/RPC2" % (USER, TOKEN, HOSTNAME)
    )
    data = connection.results.run_query(QUERY, 20, QUERY_USER)
    if not data:
        return 0
    print("Job, Type, Message, Time")
    for result in data:
        job_lava = yaml.safe_load(
            connection.results.get_testcase_results_yaml(result["id"], "lava", "job")
        )[0]
        job_id = job_lava["job"]
        logged = job_lava["logged"]
        if result["status"] == INCOMPLETE:
            error_type = job_lava["metadata"]["error_type"]
            msg = job_lava["metadata"]["error_msg"]
            print("%s, '%s', '%s', '%s'" % (job_id, error_type, msg, logged))
            continue
        elif result["status"] == COMPLETE:
            continue
        print("[%s] %s" % (job_lava["job"], STATUS_CHOICES[int(result["status"])][1]))
    return 0


# end main_function


if __name__ == "__main__":
    sys.exit(main(sys.argv))
