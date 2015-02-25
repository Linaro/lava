from lava_scheduler_app.models import Device, DeviceType, DeviceDictionary, JobPipeline
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


class DeviceDictionaryTest(TestCaseWithFactory):
    """
    Test the Device Dictionary KVStore
    """

    def test_new_dictionary(self):
        foo = DeviceDictionary(hostname='foo')
        foo.save()
        self.assertEqual(foo.hostname, 'foo')

    def test_dictionary_parameters(self):
        foo = DeviceDictionary(hostname='foo')
        foo.parameters = {
            'bootz': {
                'kernel': '0x4700000',
                'ramdisk': '0x4800000',
                'dtb': '0x4300000'
            },
            'media': {
                'usb': {
                    'UUID-required': True,
                    'SanDisk_Ultra': {
                        'uuid': 'usb-SanDisk_Ultra_20060775320F43006019-0:0',
                        'device_id': 0
                    },
                    'sata': {
                        'UUID-required': False
                    }
                }
            }
        }
        foo.save()
        bar = DeviceDictionary.get('foo')
        self.assertEqual(bar.parameters, foo.parameters)

    def test_dictionary_remove(self):
        foo = DeviceDictionary(hostname='foo')
        foo.parameters = {
            'bootz': {
                'kernel': '0x4700000',
                'ramdisk': '0x4800000',
                'dtb': '0x4300000'
            },
        }
        foo.save()
        baz = DeviceDictionary.get('foo')
        self.assertEqual(baz.parameters, foo.parameters)
        baz.delete()
        self.assertIsInstance(baz, DeviceDictionary)
        baz = DeviceDictionary.get('foo')
        self.assertIsNone(baz)


class JobPipelineTest(TestCaseWithFactory):
    """
    Test that the JobPipeline KVStore is separate from the Device Dictionary KVStore.
    """
    def test_new_dictionary(self):
        foo = JobPipeline.get('foo')
        self.assertIsNone(foo)
        foo = DeviceDictionary(hostname='foo')
        foo.save()
        self.assertEqual(foo.hostname, 'foo')
        self.assertIsInstance(foo, DeviceDictionary)
        foo = DeviceDictionary.get('foo')
        self.assertIsNotNone(foo)
        foo = JobPipeline(job_id=4212)
        foo.save()
        foo = JobPipeline.get('foo')
        self.assertIsNotNone(foo)
        self.assertIsInstance(foo, JobPipeline)
