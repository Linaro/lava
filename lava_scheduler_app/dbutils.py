"""
Database utility functions which use but are not actually models themselves
Used to allow models.py to be shortened and easier to follow.
"""

# pylint: disable=wrong-import-order

import os
import yaml
import jinja2
import json
import logging
from django.db.models import Q, Case, When, IntegerField, Sum
from lava_scheduler_app.models import (
    Device,
    TestJob,
    validate_job,
    validate_device,
    Worker
)
from lava_results_app.dbutils import map_metadata

# pylint: disable=too-many-branches,too-many-statements,too-many-locals


def match_vlan_interface(device, job_def):
    if not isinstance(job_def, dict):
        raise RuntimeError("Invalid vlan interface data")
    if 'protocols' not in job_def or 'lava-vland' not in job_def['protocols'] or not device:
        return False
    interfaces = []
    logger = logging.getLogger('lava-master')
    device_dict = device.load_configuration()
    if not device_dict or device_dict.get('parameters', {}).get('interfaces', None) is None:
        return False

    for vlan_name in job_def['protocols']['lava-vland']:
        tag_list = job_def['protocols']['lava-vland'][vlan_name]['tags']
        for interface in device_dict['parameters']['interfaces']:
            tags = device_dict['parameters']['interfaces'][interface]['tags']
            if not tags:
                continue
            logger.info(
                "Job requests %s for %s, device %s provides %s for %s",
                tag_list, vlan_name, device.hostname, tags, interface)
            if set(tags) & set(tag_list) == set(tag_list) and interface not in interfaces:
                logger.info("Matched vlan %s to interface %s on %s", vlan_name, interface, device)
                interfaces.append(interface)
                # matched, do not check any further interfaces of this device for this vlan
                break

    logger.info("Matched: %s", (len(interfaces) == len(job_def['protocols']['lava-vland'].keys())))
    return len(interfaces) == len(job_def['protocols']['lava-vland'].keys())


# TODO: check the list of exception that can be raised
def testjob_submission(job_definition, user, original_job=None):
    """
    Single submission frontend for YAML
    :param job_definition: string of the job submission
    :param user: user attempting the submission
    :return: a job or a list of jobs
    :raises: SubmissionException, Device.DoesNotExist,
        DeviceType.DoesNotExist, DevicesUnavailableException,
        ValueError
    """
    json_data = True
    try:
        # accept JSON but store as YAML
        json.loads(job_definition)
    except json.decoder.JSONDecodeError:
        json_data = False
    if json_data:
        # explicitly convert to YAML.
        # JSON cannot have comments anyway.
        job_definition = yaml.safe_dump(yaml.safe_load(job_definition))

    validate_job(job_definition)
    # returns a single job or a list (not a QuerySet) of job objects.
    job = TestJob.from_yaml_and_user(job_definition, user, original_job=original_job)
    return job


def parse_job_description(job):
    filename = os.path.join(job.output_dir, 'description.yaml')
    logger = logging.getLogger('lava-master')
    try:
        with open(filename, 'r') as f_describe:
            description = f_describe.read()
        pipeline = yaml.load(description)
    except (IOError, yaml.YAMLError):
        logger.error("'Unable to open and parse '%s'", filename)
        return

    if not map_metadata(description, job):
        logger.warning("[%d] unable to map metadata", job.id)

    # add the compatibility result from the master to the definition for comparison on the slave.
    try:
        compat = int(pipeline['compatibility'])
    except (TypeError, ValueError):
        compat = pipeline['compatibility'] if pipeline is not None else None
        logger.error("[%d] Unable to parse job compatibility: %s",
                     job.id, compat)
        compat = 0
    job.pipeline_compatibility = compat
    job.save(update_fields=['pipeline_compatibility'])


def device_type_summary(visible=None):
    devices = Device.objects.filter(
        ~Q(health=Device.HEALTH_RETIRED) & Q(device_type__in=visible)).only(
            'state', 'health', 'is_public', 'device_type', 'hostname').values('device_type').annotate(
                idle=Sum(
                    Case(
                        When(state=Device.STATE_IDLE, health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN], worker_host__state=Worker.STATE_ONLINE, then=1),
                        default=0, output_field=IntegerField()
                    )
                ),
                busy=Sum(
                    Case(
                        When(state__in=[Device.STATE_RESERVED, Device.STATE_RUNNING], then=1),
                        default=0, output_field=IntegerField()
                    )
                ),
                offline=Sum(
                    Case(
                        When(Q(state=Device.STATE_IDLE) & (Q(worker_host__state=Worker.STATE_OFFLINE) | ~Q(health__in=[Device.HEALTH_GOOD, Device.HEALTH_UNKNOWN])),
                             then=1),
                        default=0, output_field=IntegerField()
                    )
                ),
                restricted=Sum(
                    Case(
                        When(is_public=False, then=1),
                        default=0, output_field=IntegerField()
                    )
                ),).order_by('device_type')
    return devices


def load_devicetype_template(device_type_name, raw=False):
    """
    Loads the bare device-type template as a python dictionary object for
    representation within the device_type templates.
    No device-specific details are parsed - default values only, so some
    parts of the dictionary may be unexpectedly empty. Not to be used when
    rendering device configuration for a testjob.
    :param device_type_name: DeviceType.name (string)
    :param raw: if True, return the raw yaml
    :return: None or a dictionary of the device type template.
    """
    path = os.path.dirname(Device.CONFIG_PATH)
    type_loader = jinja2.FileSystemLoader([os.path.join(path, 'device-types')])
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader([type_loader]),
        trim_blocks=True)
    try:
        template = env.get_template("%s.jinja2" % device_type_name)
        data = template.render()
        if not data:
            return None
        return data if raw else yaml.safe_load(data)
    except (jinja2.TemplateError, yaml.error.YAMLError):
        return None


def invalid_template(dt):
    """
    Careful with the inverted logic here.
    Return True if the template is invalid.
    See unit tests in test_device.py
    """
    d_template = bool(load_devicetype_template(dt.name))  # returns None on error ( == False)
    if not d_template:
        queryset = list(Device.objects.filter(Q(device_type=dt), ~Q(health=Device.HEALTH_RETIRED)))
        if not queryset:
            return False
        extends = set([device.get_extends() for device in queryset])
        if not extends:
            return True
        for extend in extends:
            if not extend:
                return True
            d_template = not bool(load_devicetype_template(extend.replace('.jinja2', '')))
            # if d_template is False, template is valid, invalid_template returns False
            if d_template:
                return True
    else:
        d_template = False  # template exists, invalid check is False
    return d_template
