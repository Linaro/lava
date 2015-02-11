from lava_scheduler_app.models import Device, DeviceType
from django_testscenarios.ubertest import TestCase
from django.contrib.auth.models import Group, Permission, User


class ModelFactory(object):

    def __init__(self):
        self._int = 0

    def getUniqueInteger(self):
        self._int += 1
        return self._int

    def getUniqueString(self, prefix='generic'):
        return '%s-%d' % (prefix, self.getUniqueInteger())

    def make_user(self):
        return User.objects.create_user(
            self.getUniqueString(),
            '%s@mail.invalid' % (self.getUniqueString(),),
            self.getUniqueString())


class TestCaseWithFactory(TestCase):

    def setUp(self):
        TestCase.setUp(self)
        self.factory = ModelFactory()


class DeviceTest(TestCaseWithFactory):

    def test_put_into_looping_mode(self):
        foo = DeviceType(name='foo')
        device = Device(device_type=foo, hostname='foo01', status=Device.OFFLINE)
        device.save()

        device.put_into_looping_mode(None, None)

        self.assertEqual(device.status, Device.IDLE, "should be IDLE")
        self.assertEqual(device.health_status, Device.HEALTH_LOOPING, "should be LOOPING")

    def test_access_while_hidden(self):
        hidden = DeviceType(name="hidden", owners_only=True, health_check_job='')
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
        hidden = DeviceType(name="hidden", owners_only=True, health_check_job='')
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
