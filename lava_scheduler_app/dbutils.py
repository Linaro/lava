"""
Database utility functions which use but are not actually models themselves
Used to allow models.py to be shortened and easier to follow.
"""
import logging
from lava_scheduler_app.models import DeviceDictionary


def match_vlan_interface(device, job_def):
    if not isinstance(job_def, dict):
        raise RuntimeError("Invalid vlan interface data")
    if 'protocols' not in job_def or 'lava-vland' not in job_def['protocols']:
        return False
    interfaces = []
    logger = logging.getLogger('lava_scheduler_app')
    for vlan_name in job_def['protocols']['lava-vland']:
        tag_list = job_def['protocols']['lava-vland'][vlan_name]['tags']
        device_dict = DeviceDictionary.get(device.hostname).to_dict()
        if 'tags' not in device_dict['parameters']:
            return False
        for interface, tags in device_dict['parameters']['tags'].iteritems():
            if any(set(tags).intersection(tag_list)) and interface not in interfaces:
                logger.debug("Matched vlan %s to interface %s on %s", vlan_name, interface, device)
                interfaces.append(interface)
                # matched, do not check any further interfaces of this device for this vlan
                break
    return len(interfaces) == len(job_def['protocols']['lava-vland'].keys())
