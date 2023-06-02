# Copyright (C) 2013-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Senthil Kumaran <senthil.kumaran@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import copy
import errno
import ipaddress
import os
import subprocess  # nosec verified

from django.conf import settings
from django.contrib.auth.models import User
from django.template.defaultfilters import truncatechars

from lava_scheduler_app.schema import SubmissionException

DEFAULT_IRC_SERVER = "irc.freenode.net"
DEFAULT_IRC_PORT = 6667

SERVICE_UNKNOWN_ERROR = "service not known"
NO_SUCH_NICK_ERROR = "No such nick/channel"


class IRCSendError(Exception):
    """Global IRC error."""


class IRCServerIncorrectError(IRCSendError):
    """Error raised when IRC server name is erroneous."""


class IRCHandleNotFoundError(IRCSendError):
    """Error raised when user handle is not found on specific server."""


def _split_multinode_vland(submission, jobs):
    for role, _ in jobs.items():
        # populate the lava-vland protocol metadata
        if len(jobs[role]) != 1:
            raise SubmissionException(
                "vland protocol only supports one device per role."
            )
        jobs[role][0]["protocols"].update(
            {"lava-vland": submission["protocols"]["lava-vland"][role]}
        )
    return jobs


def split_multinode_yaml(submission, target_group):
    """
    Handles the lava-multinode protocol requirements.
    Uses the multinode protocol requirements to generate as many YAML
    snippets as are required to create TestJobs for the multinode submission.
    Each multinode YAML submission is only split once for all roles and all sub jobs.
    parameters:
      submission - the dictionary of the submission YAML.
      device_dict - the dictionary mapping device hostnames to roles
      target_group - the uuid of the multinode group
    return:
      None on error or a dictionary of job roles.
      key: role
      value: list of jobs to be created for that role.
    """
    # the list of devices cannot be definite here, only after devices have been reserved

    # FIXME: needs a Protocol base class in the server and protocol-specific split handlers

    copies = [
        "job_name",
        "timeouts",
        "priority",
        "visibility",
        "notify",
        "metadata",
        "reboot_to_fastboot",
    ]
    skip = ["role", "roles"]
    scheduling = [
        "device_type",
        "connection",
        "host_role",
        "context",
    ]  # top level values to be preserved
    maps = ["count"]  # elements to be matched but not listed at top level.

    roles = {}
    actions = {}
    subid = 0

    # FIXME: check structure using a schema

    role_data = submission["protocols"]["lava-multinode"]["roles"]
    group_size = sum(
        [
            role_data[count]["count"]
            for count in role_data
            if "count" in role_data[count]
        ]
    )

    # populate the lava-multinode protocol metadata
    for role, value in submission["protocols"]["lava-multinode"]["roles"].items():
        roles[role] = {}
        for item in copies:
            if item in submission:
                roles[role][item] = submission[item]
        for name in maps:
            if name in value:
                roles[role][name] = value[name]
        for name in scheduling:
            if name in value:
                roles[role][name] = value[name]
        tags = set(value) - set(maps) - set(scheduling)
        params = {
            "target_group": target_group,
            "role": role,
            "group_size": group_size,
            "sub_id": subid,
        }
        if "essential" in value:
            params["essential"] = value
        for tag in tags:
            params[tag] = value[tag]
        roles[role].update({"protocols": {"lava-multinode": params}})
        subid += 1

    # split the submission based on the roles specified for the actions, retaining order.
    for role in roles:
        for action in submission["actions"]:
            for key, value in action.items():
                try:
                    value["role"]
                except (KeyError, TypeError):
                    raise SubmissionException(
                        "Invalid YAML - Did not find a role in action '%s', check for consistent use of whitespace indents."
                        % next(iter(action.keys()))
                    )
                if role in value["role"]:
                    actions.setdefault(role, {"actions": []})
                    actions[role]["actions"].append(
                        {copy.deepcopy(key): copy.deepcopy(value)}
                    )

    # add other parameters from the lava-multinode protocol
    for key, value in submission["protocols"]["lava-multinode"].items():
        if key in skip:
            continue
        for role in roles:
            roles[role]["protocols"]["lava-multinode"][key] = value

    # set the role for each action to the role of the job instead of the original list..
    for role in actions:
        for action in actions[role]["actions"]:
            for key, value in action.items():
                value["role"] = role

    # jobs dictionary lists the jobs per role,
    jobs = {}
    # check the count of the host_roles
    check_count = None
    for role in roles:
        if "host_role" in roles[role]:
            check_count = roles[role]["host_role"]
    for role in roles:
        if role == check_count:
            if roles[role]["count"] != 1:
                raise SubmissionException(
                    "The count for a role designated as a host_role must be 1."
                )
    sub_id_count = 0
    for role in roles:
        jobs[role] = []
        for sub in range(0, roles[role]["count"]):
            job = {}
            job.update(actions[role])
            job.update(roles[role])
            # only here do multiple jobs for the same role differ
            params = job["protocols"]["lava-multinode"]
            params.update({"sub_id": sub_id_count})
            job["protocols"]["lava-multinode"].update(params)
            del params
            for item in maps:
                if item in job:
                    del job[item]
            jobs[role].append(copy.deepcopy(job))
            sub_id_count += 1

    # populate the lava-vland protocol metadata
    if "lava-vland" in submission["protocols"]:
        _split_multinode_vland(submission, jobs)

    # populate the lava-lxc protocol data
    if "lava-lxc" in submission["protocols"]:
        for role, _ in jobs.items():
            if role not in submission["protocols"]["lava-lxc"]:
                continue
            # populate the lava-lxc protocol metadata
            for job in jobs[role]:
                job["protocols"].update(
                    {"lava-lxc": submission["protocols"]["lava-lxc"][role]}
                )

    return jobs


def mkdir(path):
    try:
        os.makedirs(path, mode=0o755)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def send_irc_notification(
    nick, recipient, message, server=DEFAULT_IRC_SERVER, port=DEFAULT_IRC_PORT
):
    """
    Sends private IRC msg with netcat.
    parameters:
      server - the IRC server where the recipient is.
      port - server port used for the communication.
      nick - nick that sends the message.
      recipient - recipient handle.
      message - message content.
    raise:
      If there is an error, raise an exception and pass stderr message.
    """

    netcat_cmd = (
        "echo -e 'NICK %s\nUSER %s 8 * %s\nPRIVMSG %s :%s\nQUIT\n' | nc -i 5 -q 15 %s %s"
        % (nick, nick, nick, recipient, message, server, port)
    )

    proc = subprocess.Popen(  # nosec managed.
        ["/bin/bash", "-c", netcat_cmd],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if proc.stderr:
        with proc.stderr:
            for line in iter(proc.stderr.readline, b""):
                if SERVICE_UNKNOWN_ERROR in line:
                    raise IRCServerIncorrectError(line)
                else:
                    raise IRCSendError(line)

    with proc.stdout:
        for line in iter(proc.stdout.readline, b""):
            if NO_SUCH_NICK_ERROR in line:
                raise IRCHandleNotFoundError(line)
    proc.wait()


def get_ldap_user_properties(ldap_user):
    """Searches LDAP based on the parameters in settings.conf and returns LDAP
    user properties as a dictionary, eg:

    {uid: 'senthil.kumaran',
     mail: 'senthil.kumaran@linaro.org',
     sn: 'Kumaran',
     given_name: 'Senthil'
    }

    If given ldap_user does not exist, then raise ldap.NO_SUCH_OBJECT.
    Raise ldap.UNAVAILABLE if LDAP authentication not configured.
    """
    import ldap

    server_uri = settings.AUTH_LDAP_SERVER_URI
    bind_dn = settings.AUTH_LDAP_BIND_DN
    bind_password = settings.AUTH_LDAP_BIND_PASSWORD
    user_dn_template = settings.AUTH_LDAP_USER_DN_TEMPLATE
    user_search = settings.AUTH_LDAP_USER_SEARCH

    search_scope = ldap.SCOPE_SUBTREE
    attributes = ["uid", "givenName", "sn", "mail"]
    search_filter = "cn=*"

    if user_dn_template:
        user_dn = user_dn_template % {"user": ldap_user}
    if user_search is not None:
        from django_auth_ldap.config import LDAPSearch

        user_dn = user_search.base_dn
        search_filter = user_search.filterstr % {"user": ldap_user}

    user_properties = {}
    if server_uri is not None:
        conn = ldap.initialize(server_uri)
        if user_dn:
            conn.simple_bind_s(bind_dn, bind_password)
            try:
                result = conn.search_s(user_dn, search_scope, search_filter, attributes)
                if len(result) == 1:
                    result_type, result_data = result[0]
                    user_properties["uid"] = result_data.get("uid", [None])[0]
                    user_properties["mail"] = result_data.get("mail", [None])[0]
                    user_properties["sn"] = result_data.get("sn", [None])[0]
                    user_properties["given_name"] = result_data.get(
                        "givenName", [None]
                    )[0]

                    user_properties = {
                        k: v.decode() for (k, v) in user_properties.items()
                    }

                    # Grab max_length and truncate first and last name.
                    # For some users, first or last name is too long to create.
                    first_name_max_length = User._meta.get_field(
                        "first_name"
                    ).max_length
                    last_name_max_length = User._meta.get_field("last_name").max_length
                    user_properties["sn"] = truncatechars(
                        user_properties["sn"], last_name_max_length
                    )
                    user_properties["given_name"] = truncatechars(
                        user_properties["given_name"], first_name_max_length
                    )

                    return user_properties
                elif len(result) == 0:
                    raise ldap.NO_SUCH_OBJECT
            except ldap.NO_SUCH_OBJECT:
                raise
    else:
        raise ldap.UNAVAILABLE


def get_user_ip(request):
    if "HTTP_X_FORWARDED_FOR" in request.META:
        ips = [
            ip.strip(" ")
            for ip in request.META["HTTP_X_FORWARDED_FOR"].split(",")
            if ip
        ]
        with contextlib.suppress(IndexError):
            return ips[settings.HTTP_X_FORWARDED_FOR_INDEX]
        return None
    return None


def is_ip_allowed(ip, rules):
    user_ip = ipaddress.ip_address(ip)
    # Check against the rules
    for rule in rules:
        if user_ip in ipaddress.ip_network(rule):
            return True
    return False
