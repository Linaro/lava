import re
import sys
import yaml
from voluptuous import (
    All,
    Any,
    Exclusive,
    Invalid,
    Length,
    Match,
    MultipleInvalid,
    Optional,
    Required,
    Schema
)

if sys.version_info[0] == 2:
    # Python 2.x
    from urllib2 import urlopen
    from urllib2 import URLError
elif sys.version_info[0] == 3:
    # For Python 3.0 and later
    from urllib.request import urlopen
    from urllib.error import URLError


INVALID_CHARACTER_ERROR_MSG = "Invalid character"
INCLUDE_URL_TIMEOUT = 10


class SubmissionException(UserWarning):
    """ Error raised if the submission is itself invalid. """


def _timeout_schema():
    return Schema({
        Exclusive('days', 'timeout_unit'): int,
        Exclusive('hours', 'timeout_unit'): int,
        Exclusive('minutes', 'timeout_unit'): int,
        Exclusive('seconds', 'timeout_unit'): int
    })


def _deploy_tftp_schema():
    return Schema({
        Required('to'): 'tftp',
        Optional('timeout'): _timeout_schema(),
        Optional('kernel'): {Required('url'): str},
        Optional('ramdisk'): {Required('url'): str},
        Optional('nbdroot'): {Required('url'): str},
        Optional('initrd'): {Required('url'): str},
        Optional('nfsrootfs'): {Required('url'): str},
        Optional('dtb'): {Required('url'): str},
        Optional('modules'): {Required('url'): str},
    }, extra=True)


def _job_deploy_schema():
    return Schema({
        Required('to'): str,
        Optional('timeout'): _timeout_schema(),
    }, extra=True)


def _auto_login_schema():
    return Schema({
        Required('login_prompt'): str,
        Required('username'): str,
        Optional('password_prompt'): str,
        Optional('password'): str,
        Optional('login_commands'): list,
    })


def _simple_params():
    return Schema({
        Any(str): Any(str, bool)
    })


def _context_schema():
    return Schema({
        Optional('arch'): str,
        Optional('memory'): int,
        Optional('netdevice'): str,
        Optional('extra_options'): list
    }, extra=True)


def _job_boot_schema():
    return Schema({
        Required('method'): str,
        Optional('timeout'): _timeout_schema(),
        Optional('auto_login'): _auto_login_schema(),
        Optional('parameters'): _simple_params(),
    }, extra=True)


def _inline_schema():
    return Schema({
        'metadata': dict,
        'install': dict,
        'run': dict,
        'parse': dict
    })


def _test_definition_schema():
    return Schema([
        {
            Required('repository'): Any(_inline_schema(), str),
            Required('from'): str,
            Required('name'): str,
            Required('path'): str,
            Optional('parameters'): dict,
        }
    ], extra=True)


def _job_test_schema():
    return Schema({
        Required('definitions'): _test_definition_schema(),
        Optional('timeout'): _timeout_schema(),
    }, extra=True)


def _job_monitor_schema():
    return Schema({
        Required('monitors'): _monitor_def_schema(),
        Optional('timeout'): _timeout_schema()
    }, extra=True)


def _monitor_def_schema():
    return Schema([
        {
            Required('name'): Match(r'^[a-zA-Z0-9-_]+$',
                                    msg=INVALID_CHARACTER_ERROR_MSG),
            Required('start'): str,
            Required('end'): str,
            Required('pattern'): str,
            Optional('fixupdict'): dict
        }
    ])


def _job_command_schema():
    return Schema({
        Required('name'): str,
        Optional('timeout'): _timeout_schema()
    })


def _job_actions_schema():
    return Schema([
        {
            'deploy': Any(
                _deploy_tftp_schema(),
                _job_deploy_schema()),
            'boot': _job_boot_schema(),
            'test': Any(_job_monitor_schema(),
                        _job_test_schema()),
            'command': _job_command_schema()
        }
    ])


def _job_notify_schema():
    return Schema({
        Required('criteria'): _notify_criteria_schema(),
        'recipients': _recipient_schema(),
        'callback': _callback_schema(),
        'verbosity': Any('verbose', 'quiet', 'status-only'),
        'compare': _notify_compare_schema()
    }, extra=True)


def _recipient_schema():
    from lava_scheduler_app.models import NotificationRecipient
    return Schema([
        {
            Required('to'): {
                Required('method'): Any(NotificationRecipient.EMAIL_STR,
                                        NotificationRecipient.IRC_STR),
                'user': str,
                'email': str,
                'server': str,
                'handle': str
            }
        }
    ])


def _notify_criteria_schema():
    return Schema({
        Required('status'): Any('running', 'complete', 'incomplete',
                                'canceled', 'finished'),
        'type': Any('progression', 'regression')
    }, extra=True)


def _notify_compare_schema():
    return Schema({
        'query': Any(_query_name_schema(), _query_conditions_schema()),
        'blacklist': [str]
    }, extra=True)


def _query_name_schema():
    return Schema({
        Required('username'): str,
        Required('name'): str
    })


def _query_conditions_schema():
    return Schema({
        Required('entity'): str,
        'conditions': dict
    })


def _callback_schema():
    return Schema({
        'method': Any('GET', 'POST'),
        Required('url'): str,
        'token': str,
        'dataset': Any('minimal', 'logs', 'results', 'all'),
        'content-type': Any('json', 'urlencoded')
    }, extra=True)


def vlan_name(value):
    if re.match("^[_a-zA-Z0-9]+$", str(value)):
        return str(value)
    else:
        raise Invalid(value)


def _job_protocols_schema():
    return Schema({
        'lava-multinode': {
            'timeout': _timeout_schema(),
            'roles': dict
        },
        'lava-vland': {
            str: {
                vlan_name: {
                    'tags': [
                        str
                    ],
                }
            }
        },
        'lava-lxc': dict,
        'lava-xnbd': dict
    })


def action_name(value):
    if re.match(r'^[a-z-]+$', str(value)):
        return str(value)
    else:
        raise Invalid(value)


def _job_timeout_schema():
    return Schema({
        Required('job'): _timeout_schema(),
        Optional('action'): _timeout_schema(),
        Optional('connection'): _timeout_schema(),
        Optional('actions'): {
            All(action_name): _timeout_schema()
        },
        Optional('connections'): {
            All(action_name): _timeout_schema()
        },
    })


def visibility_schema():
    # possible values - 1 of 2 strings or a specified dict
    return Schema(Any('public', 'personal', {'group': [str]}))


def _job_schema():
    return Schema(
        {
            'device_type': All(str, Length(min=1)),  # not Required as some protocols encode it elsewhere
            Required('job_name'): All(str, Length(min=1, max=200)),
            Optional('include'): str,
            Optional('priority'): Any('high', 'medium', 'low'),
            Optional('protocols'): _job_protocols_schema(),
            Optional('context'): _context_schema(),
            Optional('metadata'): All({Any(str, int): Any(str, int)}),
            Optional('secrets'): dict,
            Optional('tags'): [str],
            Required('visibility'): visibility_schema(),
            Required('timeouts'): _job_timeout_schema(),
            Required('actions'): _job_actions_schema(),
            Optional('notify'): _job_notify_schema(),
            Optional('reboot_to_fastboot'): bool
        }
    )


def _device_deploy_schema():
    return Schema({
        'connections': dict,
        Required('methods'): dict,
        Optional('parameters'): _simple_params(),
    })


def _device_boot_schema():
    return Schema({
        Required('connections'): dict,
        Required('methods'): dict,
    })


def _device_actions_schema():
    return Schema({
        'deploy': _device_deploy_schema(),
        'boot': _device_boot_schema(),
    })


def _device_timeouts_schema():
    return Schema({
        Optional('actions'): {
            All(action_name): _timeout_schema()
        },
        Optional('connections'): {
            All(action_name): _timeout_schema()
        }
    })


def _device_user_commands():
    return Schema({
        All(str): {
            Required('do'): str,
            Optional('undo'): str
        }
    })


def _device_connections_commands():
    return Schema({
        All(str): {
            'connect': str,
            Optional('tags'): list
        }
    })


def _device_commands_schema():
    return Schema({
        All(str): Any(list, dict, str),
        Optional('connections'): _device_connections_commands(),
        Optional('users'): _device_user_commands()
    })


def _device_schema():
    """
    Less strict than the job_schema as this is primarily admin / template controlled.
    """
    return Schema({
        'character_delays': dict,
        'commands': _device_commands_schema(),
        'constants': dict,
        'adb_serial_number': str,
        'fastboot_serial_number': str,
        'fastboot_options': [str],
        'fastboot_via_uboot': bool,
        'device_info': [dict],
        'static_info': [dict],
        'flash_cmds_order': list,
        'device_type': All(str, Length(min=1)),
        'parameters': dict,
        'board_id': str,
        'usb_vendor_id': All(str, Length(min=4, max=4)),  # monitor type like arduino
        'usb_product_id': All(str, Length(min=4, max=4)),  # monitor type like arduino
        'usb_filesystem_label': str,
        'usb_serial_driver': str,
        'actions': _device_actions_schema(),
        'timeouts': _device_timeouts_schema(),
        'available_architectures': list
    })


def _validate_secrets(data_object):
    if 'secrets' in data_object:
        if data_object['visibility'] == 'public':
            raise SubmissionException("When 'secrets' is used, 'visibility' shouldn't be 'public'")


def _validate_vcs_parameters(data_objects):
    for action in data_objects['actions']:
        if 'test' in action and 'definitions' in action['test']:
            for definition in action['test']['definitions']:
                if 'revision' in definition and \
                   'shallow' in definition and definition['shallow'] is True:
                    raise SubmissionException("When 'revision' is used, 'shallow' shouldn't be 'True'")


def _download_raw_yaml(url):
    try:
        data = yaml.load(
            urlopen(url, timeout=INCLUDE_URL_TIMEOUT).read())
        return data
    except URLError as e:
        raise SubmissionException(
            "Section 'include' must contain valid URL: %s" % e)
    except yaml.YAMLError as e:
        raise SubmissionException("Section 'include' must contain URL to a raw file in valid YAML format: %s" % e)


def include_yaml(data_object, include_data):

    if not isinstance(include_data, dict):
        raise SubmissionException("Include section must be a dictionary.")

    for key in include_data:
        if key not in data_object:
            data_object[key] = include_data[key]
        else:
            if isinstance(data_object[key], dict):
                data_object[key].update(include_data[key])
            elif isinstance(data_object[key], list):
                data_object[key] += include_data[key]
            elif isinstance(data_object[key], str):
                data_object[key] = include_data[key]

    return data_object


def handle_include_option(data_object):
    if 'include' in data_object:
        include_data = _download_raw_yaml(data_object['include'])
        include_yaml(data_object, include_data)

    return data_object


def validate_submission(data_object):
    """
    Validates a python object as a TestJob submission
    :param data: Python object, e.g. from yaml.load()
    :return: True if valid, else raises SubmissionException
    """
    try:
        data_object = handle_include_option(data_object)
        schema = _job_schema()
        schema(data_object)
    except MultipleInvalid as exc:
        raise SubmissionException(exc)

    _validate_secrets(data_object)
    _validate_vcs_parameters(data_object)
    return True


def _validate_primary_connection_power_commands(data_object):
    power_control_commands = [
        'power_off',
        'power_on',
        'hard_reset'
    ]

    # debug, tests don't pass. write docs.
    try:
        ssh_host = data_object['actions']['deploy']['methods']['ssh']['host']
        if ssh_host:
            if 'commands' in data_object:
                for command in power_control_commands:
                    if command in data_object['commands']:
                        raise SubmissionException(
                            "When primary connection is used, power control commands (%s) should not be specified." % ", ".join(power_control_commands))
    except KeyError:
        pass  # no primary connection setup, skip


def validate_device(data_object):
    """
    Validates a python object as a pipeline device configuration
    e.g. yaml.load(`lava-server manage device-dictionary --hostname host1 --export`)
    To validate a device_type template, a device dictionary needs to be created.
    :param data: Python object representing a pipeline Device.
    :return: True if valid, else raises SubmissionException
    """
    try:
        schema = _device_schema()
        schema(data_object)
    except MultipleInvalid as exc:
        raise SubmissionException(exc)

    _validate_primary_connection_power_commands(data_object)
    return True
