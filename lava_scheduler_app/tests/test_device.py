# pylint: disable=ungrouped-imports

import os
import yaml
import jinja2
import logging
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from lava_scheduler_app.models import (
    Device,
    DeviceType,
)
from lava_scheduler_app.dbutils import load_devicetype_template
from lava_scheduler_app.schema import validate_device
from django_testscenarios.ubertest import TestCase
from django.contrib.auth.models import User
from lava_dispatcher.pipeline.device import PipelineDevice

# pylint: disable=blacklisted-name,too-many-ancestors,invalid-name
# python3 needs print to be a function, so disable pylint
# pylint: disable=superfluous-parens
# pylint: disable=too-many-branches,too-many-locals,too-many-nested-blocks


class ModelFactory(object):

    def __init__(self):
        self._int = 0

    def getUniqueInteger(self):
        self._int += 1
        return self._int

    def getUniqueString(self, prefix='generic'):
        return '%s-%d' % (prefix, self.getUniqueInteger())

    def get_unique_user(self, prefix='generic'):  # pylint: disable=no-self-use
        return "%s-%d" % (prefix, User.objects.count() + 1)

    def make_user(self):
        return User.objects.create_user(
            self.get_unique_user(),
            '%s@mail.invalid' % (self.getUniqueString(),),
            self.getUniqueString())


class TestCaseWithFactory(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.factory = ModelFactory()


class DeviceTest(TestCaseWithFactory):

    def setUp(self):
        super(DeviceTest, self).setUp()
        logger = logging.getLogger('dispatcher-master')
        logger.disabled = True

    def test_put_into_looping_mode(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo01', status=Device.OFFLINE)
        device.save()

        device.put_into_looping_mode(None, None)

        self.assertEqual(device.status, Device.IDLE, "should be IDLE")
        self.assertEqual(device.health_status, Device.HEALTH_LOOPING, "should be LOOPING")

    def test_access_while_hidden(self):
        hidden = DeviceType(name="hidden", owners_only=True)
        device = Device(device_type=hidden, hostname='hidden1', status=Device.OFFLINE)
        user = self.factory.make_user()
        device.user = user
        device.save()
        self.assertEqual(device.is_public, False)
        self.assertEqual(device.user, user)
        user2 = self.factory.make_user()
        self.assertEqual(device.can_submit(user2), False)
        self.assertEqual(device.can_submit(user), True)

    def test_access_retired_hidden(self):
        hidden = DeviceType(name="hidden", owners_only=True)
        device = Device(device_type=hidden, hostname='hidden2', status=Device.RETIRED)
        user = self.factory.make_user()
        device.user = user
        device.save()
        self.assertEqual(device.is_public, False)
        self.assertEqual(device.user, user)
        user2 = self.factory.make_user()
        self.assertEqual(device.can_submit(user2), False)
        # user cannot submit as the device is retired
        self.assertEqual(device.can_submit(user), False)

    def test_maintenance_mode(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo01', status=Device.IDLE)
        device.save()

        device.put_into_maintenance_mode(None, None)

        self.assertEqual(device.status, Device.OFFLINE, "should be offline")

        device.status = Device.RUNNING
        device.put_into_maintenance_mode(None, None)

        self.assertEqual(device.status, Device.OFFLINING, "should be offlining")

        device.status = Device.RETIRED
        device.put_into_maintenance_mode(None, None)
        self.assertEqual(device.status, Device.RETIRED, "should be retired")

    def test_online_mode(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo02', status=Device.OFFLINE)
        device.save()
        device.put_into_online_mode(None, None)
        self.assertEqual(device.status, Device.IDLE, "should be idle")

        device.status = Device.OFFLINING
        device.put_into_online_mode(None, None)
        self.assertIsNone(device.current_job)
        self.assertEqual(device.status, Device.IDLE, "should be idle")

        device.status = Device.RETIRED
        device.put_into_online_mode(None, None)
        self.assertEqual(device.status, Device.RETIRED, "should be retired")


class DeviceTypeTest(TestCaseWithFactory):
    """
    Test loading of device-type information
    """
    def test_device_type_parser(self):
        data = load_devicetype_template('beaglebone-black')
        self.assertIsNotNone(data)
        self.assertIn('actions', data)
        self.assertIn('deploy', data['actions'])
        self.assertIn('boot', data['actions'])

    def test_device_type_templates(self):
        """
        Ensure each template renders valid YAML
        """
        jinja2_path = os.path.dirname(Device.CONFIG_PATH)
        for template_name in os.listdir(os.path.join(jinja2_path, 'device-types')):
            if not template_name.endswith('jinja2'):
                continue
            type_loader = jinja2.FileSystemLoader([os.path.join(jinja2_path, 'device-types')])
            env = jinja2.Environment(
                loader=jinja2.ChoiceLoader([type_loader]),
                trim_blocks=True)
            try:
                template = env.get_template(template_name)
            except jinja2.TemplateNotFound as exc:
                self.fail('%s: %s' % (template_name, exc))
            data = None
            try:
                data = template.render()
                yaml_data = yaml.load(data)
            except yaml.YAMLError as exc:
                print(data)  # for easier debugging - use the online yaml parser
                self.fail("%s: %s" % (template_name, exc))
            self.assertIsInstance(yaml_data, dict)


class TestLogEntry(TestCaseWithFactory):

    def setUp(self):
        super(TestLogEntry, self).setUp()
        logger = logging.getLogger('dispatcher-master')
        logger.disabled = True

    def test_create_logentry(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo01', status=Device.OFFLINE)
        device.save()

        # only unit tests should call these functions with None, None
        # if that is made a requirement of the device status functions, fix this test.
        device.put_into_looping_mode(None, None)
        self.assertEqual(device.status, Device.IDLE, "should be IDLE")
        self.assertEqual(device.health_status, Device.HEALTH_LOOPING, "should be LOOPING")
        device_ct = ContentType.objects.get_for_model(Device)
        self.assertEqual(0, len(LogEntry.objects.filter(content_type=device_ct, action_flag=2).order_by('-action_time')))

        user = self.factory.make_user()
        device.put_into_maintenance_mode(user, 'test_create_logentry')
        self.assertEqual(device.status, Device.OFFLINE, "should be OFFLINE")
        self.assertEqual(device.health_status, Device.HEALTH_UNKNOWN, "should be UNKNOWN")
        # the device state transition also creates a log entry
        self.assertEqual(2, len(LogEntry.objects.filter(content_type=device_ct, action_flag=2).order_by('-action_time')))
