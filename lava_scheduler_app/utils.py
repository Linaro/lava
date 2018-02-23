# Copyright (C) 2013 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Senthil Kumaran <senthil.kumaran@linaro.org>
#
# This file is part of LAVA Scheduler.
#
# LAVA Scheduler is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License version 3 as
# published by the Free Software Foundation
#
# LAVA Scheduler is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with LAVA Scheduler.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import copy
import errno
import jinja2
import ldap
import logging
import os
import subprocess
import yaml

from collections import OrderedDict

from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured

from lava_server.settings.getsettings import Settings

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


def get_domain():
    domain = '???'
    try:
        site = Site.objects.get_current()
    except (Site.DoesNotExist, ImproperlyConfigured):
        pass
    else:
        domain = site.domain

    return domain


def is_member(user, group):
    return user.groups.filter(name='%s' % group).exists()


def _read_log(log_path):
    logger = logging.getLogger('lava_scheduler_app')
    if not os.path.exists(log_path):
        return {}
    logs = {}
    for logfile in os.listdir(log_path):
        filepath = os.path.join(log_path, logfile)
        with open(filepath, 'r') as log_files:
            try:
                logs.update({logfile: yaml.load(log_files)})
            except yaml.YAMLError as exc:
                logger.warning(exc)
                logs.update({logfile: [{'warning': "YAML error in %s" % os.path.basename(logfile)}]})
    return logs


def folded_logs(job, section_name, sections, summary=False, increment=False):
    log_data = None
    if increment:
        latest = 0
        section_name = ''
        for item in sections:
            current = int(item.values()[0])
            log_path = os.path.join(job.output_dir, 'pipeline', item.values()[0])
            if os.path.isdir(log_path):
                latest = current if current > latest else latest
                section_name = item.keys()[0] if latest == current else section_name
        if not section_name:
            return log_data
    logs = {}
    initialise_log = os.path.join(job.output_dir, 'pipeline', '0')
    if os.path.exists(initialise_log) and section_name == 'deploy':
        logs.update(_read_log(initialise_log))
    for item in sections:
        if section_name in item:
            log_path = os.path.join(job.output_dir, 'pipeline', item[section_name])
            logs.update(_read_log(log_path))
            log_keys = sorted(logs)
            log_data = OrderedDict()
            for key in log_keys:
                summary_items = [item for item in logs[key] if 'ts' in item or 'warning' in item or 'exception' in item]
                if summary_items and summary:
                    log_data[key] = summary_items
                else:
                    log_data[key] = logs[key]
    return log_data


def _split_multinode_vland(submission, jobs):

    for role, _ in jobs.items():
        # populate the lava-vland protocol metadata
        if len(jobs[role]) != 1:
            raise SubmissionException("vland protocol only supports one device per role.")
        jobs[role][0]['protocols'].update({'lava-vland': submission['protocols']['lava-vland'][role]})
    return jobs


def split_multinode_yaml(submission, target_group):  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
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
        'job_name',
        'timeouts',
        'priority',
        'visibility',
        'notify',
        'metadata',
    ]
    skip = ['role', 'roles']
    scheduling = ['device_type', 'connection', 'host_role', 'context']  # top level values to be preserved
    maps = ['count']  # elements to be matched but not listed at top level.

    roles = {}
    actions = {}
    subid = 0

    # FIXME: check structure using a schema

    role_data = submission['protocols']['lava-multinode']['roles']
    group_size = sum(
        [role_data[count]['count'] for count in role_data if 'count' in role_data[count]]
    )

    # populate the lava-multinode protocol metadata
    for role, value in submission['protocols']['lava-multinode']['roles'].items():
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
            'target_group': target_group,
            'role': role,
            'group_size': group_size,
            'sub_id': subid,
        }
        if 'essential' in value:
            params['essential'] = value
        for tag in tags:
            params[tag] = value[tag]
        roles[role].update({'protocols': {'lava-multinode': params}})
        subid += 1

    # split the submission based on the roles specified for the actions, retaining order.
    for role in roles:
        for action in submission['actions']:
            for key, value in action.items():
                try:
                    value['role']
                except (KeyError, TypeError):
                    raise SubmissionException("Invalid YAML - Did not find a role in action '%s', check for consistent use of whitespace indents." % action.keys()[0])
                if role in value['role']:
                    actions.setdefault(role, {'actions': []})
                    actions[role]['actions'].append({copy.deepcopy(key): copy.deepcopy(value)})

    # add other parameters from the lava-multinode protocol
    for key, value in submission['protocols']['lava-multinode'].items():
        if key in skip:
            continue
        for role in roles:
            roles[role]['protocols']['lava-multinode'][key] = value

    # set the role for each action to the role of the job instead of the original list..
    for role in actions:
        for action in actions[role]['actions']:
            for key, value in action.items():
                value['role'] = role

    # jobs dictionary lists the jobs per role,
    jobs = {}
    # check the count of the host_roles
    check_count = None
    for role in roles:
        if 'host_role' in roles[role]:
            check_count = roles[role]['host_role']
    for role in roles:
        if role == check_count:
            if roles[role]['count'] != 1:
                raise SubmissionException('The count for a role designated as a host_role must be 1.')
    sub_id_count = 0
    for role in roles:
        jobs[role] = []
        for sub in range(0, roles[role]['count']):
            job = {}
            job.update(actions[role])
            job.update(roles[role])
            # only here do multiple jobs for the same role differ
            params = job['protocols']['lava-multinode']
            params.update({'sub_id': sub_id_count})
            job['protocols']['lava-multinode'].update(params)
            del params
            for item in maps:
                if item in job:
                    del job[item]
            jobs[role].append(copy.deepcopy(job))
            sub_id_count += 1

    # populate the lava-vland protocol metadata
    if 'lava-vland' in submission['protocols']:
        _split_multinode_vland(submission, jobs)

    # populate the lava-lxc protocol data
    if 'lava-lxc' in submission['protocols']:
        for role, _ in jobs.items():
            if role not in submission['protocols']['lava-lxc']:
                continue
            # populate the lava-lxc protocol metadata
            jobs[role][0]['protocols'].update({'lava-lxc': submission['protocols']['lava-lxc'][role]})

    return jobs


def mkdir(path):
    try:
        os.makedirs(path, mode=0o755)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def send_irc_notification(nick, recipient, message,
                          server=DEFAULT_IRC_SERVER, port=DEFAULT_IRC_PORT):
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

    netcat_cmd = "echo -e 'NICK %s\nUSER %s 8 * %s\nPRIVMSG %s :%s\nQUIT\n' | nc -i 5 -q 15 %s %s" % (
        nick, nick, nick, recipient, message,
        server, port)

    proc = subprocess.Popen(['/bin/bash', '-c', netcat_cmd],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if proc.stderr:
        with proc.stderr:
            for line in iter(proc.stderr.readline, b''):
                if SERVICE_UNKNOWN_ERROR in line:
                    raise IRCServerIncorrectError(line)
                else:
                    raise IRCSendError(line)

    with proc.stdout:
        for line in iter(proc.stdout.readline, b''):
            if NO_SUCH_NICK_ERROR in line:
                raise IRCHandleNotFoundError(line)
    proc.wait()


def _dump_value(node):
    if isinstance(node, jinja2.nodes.Const):
        return node.as_const()

    elif isinstance(node, jinja2.nodes.Dict):
        ret = {}
        for n in node.iter_child_nodes():
            ret[n.key.as_const()] = _dump_value(n.value)
        return ret

    elif isinstance(node, (jinja2.nodes.List, jinja2.nodes.Tuple)):
        ret = []
        for n in node.iter_child_nodes():
            ret.append(_dump_value(n))
        return ret if isinstance(node, jinja2.nodes.List) else tuple(ret)


def device_dictionary_to_dict(ast):
    ret = {}

    for node in ast.find_all(jinja2.nodes.Assign):
        ret[node.target.name] = _dump_value(node.node)

    return ret


def device_dictionary_sequence():
    return [
        'power_on_command',
        'power_off_command',
        'soft_reset_command',
        'hard_reset_command',
        'pre_power_command',
        'pre_os_command',
        'adb_serial_number',
        'fastboot_options',
        'fastboot_serial_number',
        'device_info',
        'static_info',
    ]


def device_dictionary_connections():
    return [
        'connection_list',
        'connection_commands',
        'connection_tags'
    ]


def device_dictionary_vlan():
    return [
        'interfaces',
        'tags',
        'map',
        'mac_addr',
        'sysfs',
    ]


def get_ldap_user_properties(ldap_user):
    """Searches LDAP based on the parameters in settings.conf and returns LDAP
    user properties as a dictionary, eg:

    {uid: 'senthil.kumaran',
     mail: 'senthil.kumaran@linaro.org',
     sn: 'Kumaran',
     given_name: 'Senthil'
    }

    If given ldap_user does not exist, then raise ldap.NO_SUCH_OBJECT
    """
    settings = Settings("lava-server")
    server_uri = settings.get_setting("AUTH_LDAP_SERVER_URI", None)
    bind_dn = settings.get_setting("AUTH_LDAP_BIND_DN", None)
    bind_password = settings.get_setting("AUTH_LDAP_BIND_PASSWORD", None)
    user_dn_template = settings.get_setting("AUTH_LDAP_USER_DN_TEMPLATE", None)
    user_search = settings.get_setting("AUTH_LDAP_USER_SEARCH", None)

    search_scope = ldap.SCOPE_SUBTREE
    # Attributes should be byte strings
    # (see https://github.com/pyldap/pyldap/issues/68)
    attributes = [b'uid', b'givenName', b'sn', b'mail']
    search_filter = "cn=*"

    if user_dn_template:
        user_dn = user_dn_template % {'user': ldap_user}
    if user_search:
        from django_auth_ldap.config import LDAPSearch
        search = eval(user_search)
        user_dn = search.base_dn
        search_filter = search.filterstr % {'user': ldap_user}

    user_properties = {}
    if server_uri is not None:
        conn = ldap.initialize(server_uri)
        if user_dn:
            conn.simple_bind_s(bind_dn, bind_password)
            try:
                result = conn.search_s(user_dn, search_scope,
                                       search_filter, attributes)
                if len(result) == 1:
                    result_type, result_data = result[0]
                    user_properties['uid'] = result_data.get('uid', [None])[0]
                    user_properties['mail'] = result_data.get('mail',
                                                              [None])[0]
                    user_properties['sn'] = result_data.get('sn', [None])[0]
                    user_properties['given_name'] = result_data.get('givenName',
                                                                    [None])[0]
                    return user_properties
            except ldap.NO_SUCH_OBJECT:
                raise
