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
from django_testscenarios.ubertest import TestCase
from django.contrib.auth.models import User

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
        logger = logging.getLogger('lava-master')
        logger.disabled = True

    def test_access_while_private(self):
        hidden = DeviceType(name="hidden", owners_only=True)
        device = Device(device_type=hidden, hostname='hidden1', is_public=False)
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
        device = Device(device_type=hidden, hostname='hidden2', health=Device.HEALTH_RETIRED)
        user = self.factory.make_user()
        device.user = user
        device.save()
        self.assertEqual(device.is_public, False)
        self.assertEqual(device.user, user)
        user2 = self.factory.make_user()
        self.assertEqual(device.can_submit(user2), False)
        # user cannot submit as the device is retired
        self.assertEqual(device.can_submit(user), False)


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
