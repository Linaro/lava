# pylint: disable=invalid-name,logging-not-lazy
import logging
import sys
import warnings
import yaml
from dashboard_app.models import BundleStream

from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django_testscenarios.ubertest import TestCase
from django.utils import timezone

from lava_scheduler_app.models import (
    Device,
    DeviceType,
    JSONDataError,
    Tag,
    TestJob,
    DevicesUnavailableException,
    DeviceDictionary,
    _check_exclusivity,
    is_deprecated_json,
)
import simplejson

LOGGER = logging.getLogger()
LOGGER.level = logging.INFO  # change to DEBUG to see *all* output
LOGGER.addHandler(logging.StreamHandler(sys.stdout))
# filter out warnings from django sub systems like httpresponse
warnings.filterwarnings('ignore', r"Using mimetype keyword argument is deprecated")
warnings.filterwarnings('ignore', r"StrAndUnicode is deprecated")

# pylint gets confused with TestCase
# pylint: disable=no-self-use,invalid-name,too-many-ancestors,too-many-public-methods


class ModelFactory(object):

    def __init__(self):
        self._int = 0

    def getUniqueInteger(self):  # pylint: disable=invalid-name
        self._int += 1
        return self._int

    def getUniqueString(self, prefix='generic'):  # pylint: disable=invalid-name
        return '%s-%d' % (prefix, self.getUniqueInteger())

    def get_unique_user(self, prefix='generic'):  # pylint: disable=no-self-use
        return "%s-%d" % (prefix, User.objects.count() + 1)

    def cleanup(self):  # pylint: disable=no-self-use
        DeviceType.objects.all().delete()
        # make sure the DB is in a clean state wrt devices and jobs
        Device.objects.all().delete()
        TestJob.objects.all().delete()
        [item.delete() for item in DeviceDictionary.object_list()]  # pylint: disable=expression-not-assigned
        User.objects.all().delete()
        Group.objects.all().delete()

    def ensure_user(self, username, email, password):  # pylint: disable=no-self-use
        if User.objects.filter(username=username):
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(username, email, password)
            user.save()
        return user

    def make_user(self):
        return User.objects.create_user(
            self.get_unique_user(),
            '%s@mail.invalid' % (self.getUniqueString(),),
            self.getUniqueString())

    def make_group(self, name=None):
        if name is None:
            name = self.getUniqueString('name')
        return Group.objects.get_or_create(name=name)[0]

    def ensure_device_type(self, name=None):
        if name is None:
            name = self.getUniqueString('name')
        logging.debug("asking for a device_type with name %s", name)
        device_type = DeviceType.objects.get_or_create(name=name)[0]
        self.make_device(device_type)
        return device_type

    def make_device_type(self, name=None):
        if name is None:
            name = self.getUniqueString('name')
        device_type, created = DeviceType.objects.get_or_create(name=name)
        if created:
            device_type.save()
        logging.debug("asking for a device of type %s", device_type.name)
        return device_type

    def make_hidden_device_type(self, name=None):
        if name is None:
            name = self.getUniqueString('name')
        device_type, created = DeviceType.objects.get_or_create(
            owners_only=True, name=name)
        if created:
            device_type.save()
        logging.debug("asking for a device of type %s", device_type.name)
        return device_type

    def ensure_tag(self, name):  # pylint: disable=no-self-use
        return Tag.objects.get_or_create(name=name)[0]

    def make_device(self, device_type=None, hostname=None, tags=None, is_public=True, **kw):
        if device_type is None:
            device_type = self.ensure_device_type()
        if hostname is None:
            hostname = self.getUniqueString()
        if not isinstance(tags, list):
            tags = []
        # a hidden device type will override is_public
        device = Device(device_type=device_type, is_public=is_public, hostname=hostname, **kw)
        device.tags = tags
        logging.debug("making a device of type %s %s %s with tags '%s'",
                      device_type, device.is_public, device.hostname, ", ".join([x.name for x in device.tags.all()]))
        device.save()
        return device

    def make_job_data(self, actions=None, **kw):
        if not actions:
            actions = []
        data = {'actions': actions, 'timeout': 1, 'health_check': False}
        data.update(kw)
        if 'target' not in data and 'device_type' not in data:
            if DeviceType.objects.all():
                data['device_type'] = DeviceType.objects.all()[0].name
            else:
                device_type = self.ensure_device_type()
                self.make_device(device_type)
                data['device_type'] = device_type.name
        return data

    def make_job_json(self, **kw):
        return simplejson.dumps(self.make_job_data(**kw), sort_keys=True, indent=4 * ' ')

    def make_invalid_job_json(self, **kw):
        actions = [{'command': 'invalid_command'}]
        return simplejson.dumps(self.make_job_data(actions, **kw), sort_keys=True, indent=4 * ' ')

    def make_job_yaml(self, **kw):
        return yaml.dump(self.make_job_data(**kw))

    def make_testjob(self, definition=None, submitter=None, **kwargs):
        if definition is None:
            definition = self.make_job_json()
        if submitter is None:
            submitter = self.make_user()
        if 'user' not in kwargs:
            kwargs['user'] = submitter
        testjob = TestJob.from_json_and_user(definition, submitter)
        testjob.save()
        return testjob


class TestCaseWithFactory(TestCase):  # pylint: disable=too-many-ancestors

    def setUp(self):
        TestCase.setUp(self)
        self.factory = ModelFactory()


class TestTestJob(TestCaseWithFactory):  # pylint: disable=too-many-ancestors,too-many-public-methods

    def test_from_json_and_user_sets_definition(self):
        definition = self.factory.make_job_json()
        job = TestJob.from_json_and_user(definition, self.factory.make_user())
        self.assertEqual(definition, job.definition)
        self.factory.cleanup()

    def test_user_permission(self):
        self.assertIn(
            'cancel_resubmit_testjob',
            [permission.codename for permission in Permission.objects.all() if
             'lava_scheduler_app' in permission.content_type.app_label])
        user = self.factory.make_user()
        user.user_permissions.add(
            Permission.objects.get(codename='add_testjob'))
        user.save()
        self.assertEqual(user.get_all_permissions(), {u'lava_scheduler_app.add_testjob'})
        cancel_resubmit = Permission.objects.get(codename='cancel_resubmit_testjob')
        self.assertEqual('lava_scheduler_app', cancel_resubmit.content_type.app_label)
        self.assertIsNotNone(cancel_resubmit)
        self.assertEqual(cancel_resubmit.name, 'Can cancel or resubmit test jobs')
        user.user_permissions.add(cancel_resubmit)
        user.save()
        delattr(user, '_perm_cache')  # force a refresh of the user permissions as well as the user
        user = User.objects.get(username=user.username)
        self.assertEqual(
            {u'lava_scheduler_app.cancel_resubmit_testjob', u'lava_scheduler_app.add_testjob'},
            user.get_all_permissions())
        self.assertTrue(user.has_perm('lava_scheduler_app.add_testjob'))
        self.assertTrue(user.has_perm('lava_scheduler_app.cancel_resubmit_testjob'))

    def test_from_json_and_user_sets_submitter(self):
        user = self.factory.make_user()
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(), user)
        self.assertEqual(user, job.submitter)
        self.factory.cleanup()

    def test_from_json_and_user_sets_device_type(self):
        panda_type = self.factory.ensure_device_type(name='panda')
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(device_type='panda'),
            self.factory.make_user())
        self.assertEqual(panda_type, job.requested_device_type)
        self.factory.cleanup()

    def test_from_json_and_user_sets_target(self):
        panda_board = self.factory.make_device(hostname='panda01')
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(target='panda01'),
            self.factory.make_user())
        self.assertEqual(panda_board, job.requested_device)
        self.factory.cleanup()

    def test_from_json_and_user_does_not_set_device_type_from_target(self):
        panda_type = self.factory.ensure_device_type(name='panda')
        self.factory.make_device(device_type=panda_type, hostname='panda01')
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(target='panda01'),
            self.factory.make_user())
        self.assertEqual(None, job.requested_device_type)
        self.factory.cleanup()

    def test_from_json_and_user_sets_date_submitted(self):
        before = timezone.now()
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(),
            self.factory.make_user())
        after = timezone.now()
        self.assertTrue(before < job.submit_time < after)
        self.factory.cleanup()

    def test_from_json_and_user_sets_status_to_SUBMITTED(self):
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(),
            self.factory.make_user())
        self.assertEqual(job.status, TestJob.SUBMITTED)
        self.factory.cleanup()

    def test_from_json_and_user_sets_no_tags_if_no_tags(self):
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(device_tags=[]),
            self.factory.make_user())
        self.assertEqual(set(job.tags.all()), set([]))
        self.factory.cleanup()

    def test_from_json_and_user_errors_on_unknown_tags(self):
        """
        Tests that tags which are not already defined in the database
        cause job submissions to be rejected.
        """
        self.assertRaises(
            JSONDataError, TestJob.from_json_and_user,
            self.factory.make_job_json(tags=['unknown']),
            self.factory.make_user())
        self.factory.cleanup()

    def test_from_json_and_user_errors_on_unsupported_tags(self):
        """
        Tests that tags which do exist but are not defined for the
        any of the devices of the requested type cause the submission
        to be rejected with Devices Unavailable.
        """
        device_type = self.factory.ensure_device_type(name='panda')
        self.factory.make_device(device_type=device_type, hostname="panda2")
        self.factory.ensure_tag('tag1')
        self.factory.ensure_tag('tag2')
        try:
            TestJob.from_json_and_user(
                self.factory.make_job_json(tags=['tag1', 'tag2']),
                self.factory.make_user())
        except DevicesUnavailableException:
            pass
        else:
            self.fail("Device tags failure: job submitted without any devices supporting the requested tags")
        self.factory.cleanup()

    def test_from_json_and_user_sets_tag_from_device_tags(self):
        device_type = self.factory.ensure_device_type(name='panda')
        self.factory.ensure_tag('tag')
        tags = list(Tag.objects.filter(name='tag'))
        self.factory.make_device(device_type=device_type, hostname="panda1", tags=tags)
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(tags=['tag']),
            self.factory.make_user())
        self.assertEqual(
            set(tag.name for tag in job.tags.all()), {'tag'})
        self.factory.cleanup()

    def test_from_json_and_user_sets_multiple_tag_from_device_tags(self):
        device_type = self.factory.ensure_device_type(name='panda')
        tag_list = [
            self.factory.ensure_tag('tag1'),
            self.factory.ensure_tag('tag2')
        ]
        self.factory.make_device(device_type=device_type, hostname="panda2", tags=tag_list)
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(tags=['tag1', 'tag2']),
            self.factory.make_user())
        self.assertEqual(
            set(tag.name for tag in job.tags.all()), {'tag1', 'tag2'})
        self.factory.cleanup()

    def test_from_json_and_user_reuses_tag_objects(self):
        device_type = self.factory.ensure_device_type(name='panda')
        self.factory.ensure_tag('tag')
        tags = list(Tag.objects.filter(name='tag'))
        self.factory.make_device(device_type=device_type, hostname="panda3", tags=tags)
        job1 = TestJob.from_json_and_user(
            self.factory.make_job_json(tags=['tag']),
            self.factory.make_user())
        job2 = TestJob.from_json_and_user(
            self.factory.make_job_json(tags=['tag']),
            self.factory.make_user())
        self.assertEqual(
            set(tag.pk for tag in job1.tags.all()),
            set(tag.pk for tag in job2.tags.all()))
        self.factory.cleanup()

    def test_from_json_and_user_matches_available_tags(self):
        """
        Test that with more than one device of the requested type supporting
        tags, that the tag list set for the TestJob matches the list requested,
        not a shorter list from a different device or a combined list of multiple
        devices.
        """
        device_type = self.factory.ensure_device_type(name='panda')
        tag_list = [
            self.factory.ensure_tag('common_tag1'),
            self.factory.ensure_tag('common_tag2')
        ]
        self.factory.make_device(device_type=device_type, hostname="panda4", tags=tag_list)
        tag_list.append(self.factory.ensure_tag('unique_tag'))
        self.factory.make_device(device_type=device_type, hostname="panda5", tags=tag_list)
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(tags=['common_tag1', 'common_tag2', 'unique_tag']),
            self.factory.make_user())
        self.assertEqual(
            set(tag for tag in job.tags.all()),
            set(tag_list)
        )
        self.factory.cleanup()

    def test_from_json_and_user_rejects_invalid_json(self):
        self.assertRaises(
            ValueError, TestJob.from_json_and_user, '{',
            self.factory.make_user())
        self.factory.cleanup()

    def test_from_json_and_user_rejects_invalid_job(self):
        # job data must have the 'actions' and 'timeout' properties, so this
        # will be rejected.
        self.assertRaises(
            ValueError, TestJob.from_json_and_user, '{}',
            self.factory.make_user())
        self.factory.cleanup()

    def test_from_json_rejects_exclusive(self):
        panda_type = self.factory.ensure_device_type(name='panda')
        panda_board = self.factory.make_device(device_type=panda_type, hostname='panda01')
        self.assertFalse(panda_board.is_exclusive)
        job = TestJob.from_json_and_user(
            self.factory.make_job_json(device_type='panda'),
            self.factory.make_user())
        self.assertEqual(panda_type, job.requested_device_type)
        device_dict = DeviceDictionary.get(panda_board.hostname)
        self.assertIsNone(device_dict)
        device_dict = DeviceDictionary(hostname=panda_board.hostname)
        device_dict.parameters = {'exclusive': 'True'}
        device_dict.save()
        self.assertTrue(panda_board.is_exclusive)
        self.assertRaises(
            DevicesUnavailableException, _check_exclusivity, [panda_board], pipeline=False
        )
        self.factory.cleanup()

    def make_job_json_for_stream_name(self, stream_name, **kw):
        return self.factory.make_job_json(
            actions=[
                {
                    'command': 'submit_results',
                    'parameters': {
                        'server': 'http://localhost/RPC2',
                        'stream': stream_name,
                    }
                }
            ], **kw)

    def test_from_json_and_user_sets_group_from_bundlestream(self):
        group = Group.objects.create(name='group')
        user = self.factory.make_user()
        user.groups.add(group)
        b = BundleStream.objects.create(
            group=group, slug='blah', is_public=True, is_anonymous=False)
        b.save()
        self.assertEqual(group, b.group)
        j = self.make_job_json_for_stream_name(b.pathname)
        job = TestJob.from_json_and_user(j, user)
        self.assertEqual(group, job.group)
        self.factory.cleanup()

    def test_from_json_and_user_can_submit_to_anonymous(self):
        user = self.factory.make_user()
        anon_user = User.objects.get_or_create(username="anonymous-owner")[0]
        b = BundleStream.objects.create(
            slug='anonymous', is_anonymous=True, user=anon_user,
            is_public=True)
        b.save()
        j = self.make_job_json_for_stream_name('/anonymous/anonymous/')
        job = TestJob.from_json_and_user(j, user)
        self.assertEqual(user, job.submitter)
        self.factory.cleanup()

    def test_from_json_and_user_sets_is_public_from_bundlestream(self):
        group = Group.objects.create(name='group')
        user = self.factory.make_user()
        user.groups.add(group)
        b = BundleStream.objects.create(
            group=group, slug='blah', is_public=False, is_anonymous=False)
        b.save()
        j = self.make_job_json_for_stream_name(b.pathname)
        job = TestJob.from_json_and_user(j, user)
        self.assertEqual(False, job.is_public)
        self.factory.cleanup()

    def test_from_json_and_user_rejects_missing_bundlestream(self):
        user = self.factory.make_user()
        j = self.make_job_json_for_stream_name('no such stream')
        self.assertRaises(ValueError, TestJob.from_json_and_user, j, user)
        self.factory.cleanup()

    def test_from_json_and_user_rejects_inaccessible_bundlestream(self):
        stream_user = self.factory.make_user()
        job_user = self.factory.make_user()
        b = BundleStream.objects.create(
            user=stream_user, slug='blah', is_public=True, is_anonymous=False)
        b.save()
        j = self.make_job_json_for_stream_name(b.pathname)
        self.assertRaises(ValueError, TestJob.from_json_and_user, j, job_user)
        self.factory.cleanup()

    def test_anonymous_public_validation(self):
        # Anonymous streams must be public
        stream_user = self.factory.make_user()
        self.assertRaises(ValidationError, BundleStream.objects.create,
                          user=stream_user, slug='invalid', is_public=False, is_anonymous=True)
        self.factory.cleanup()

    def test_from_json_and_user_can_submit_to_group_stream(self):
        user = self.factory.make_user()
        anon_user = User.objects.get_or_create(username="anonymous-owner")[0]
        group = Group.objects.get_or_create(name="owner")[0]
        group.user_set.add(user)
        b = BundleStream.objects.create(
            slug='basic',
            is_anonymous=False,
            group=group,
            is_public=True)
        b.save()
        self.assertEqual(b.pathname, "/public/team/owner/basic/")
        j = self.make_job_json_for_stream_name(b.pathname)
        job = TestJob.from_json_and_user(j, user)
        self.assertEqual(user, job.submitter)
        self.assertEqual(True, job.is_public)
        self.assertRaises(ValueError, TestJob.from_json_and_user, j, anon_user)
        self.factory.cleanup()

    def test_restricted_submitted_job_with_group_bundle_and_multinode(self):
        """
        Need to expand this into a MultiNode test class / file with factory
        functions and add the rest of the MultiNode tests.
        """
        superuser = self.factory.make_user()
        superuser.is_superuser = True
        user = self.factory.make_user()
        anon_user = User.objects.get_or_create(username="anonymous-owner")[0]
        group = Group.objects.get_or_create(name="owner")[0]
        group.user_set.add(user)
        device_type1 = self.factory.make_device_type('hide_me_now')
        device_type2 = self.factory.make_device_type('secretive')
        device1 = self.factory.make_device(device_type=device_type1, hostname="hidden1", group=group, is_public=False)
        device1.save()
        device2 = self.factory.make_device(device_type=device_type2, hostname="terces", group=group, is_public=False)
        device2.save()
        self.assertEqual(device1.is_public, False)
        self.assertEqual(device2.is_public, False)
        b = BundleStream.objects.create(
            slug='hidden', is_anonymous=False, group=group,
            is_public=True)
        b.save()
        self.assertEqual(b.is_public, True)
        self.assertEqual(b.user, None)
        self.assertEqual(b.pathname, '/public/team/owner/hidden/')
        # singlenode must pass
        j = self.make_job_json_for_stream_name(b.pathname, target="hidden1")
        self.assertRaises(DevicesUnavailableException, TestJob.from_json_and_user, j, anon_user)
        job = TestJob.from_json_and_user(j, user)
        self.assertEqual(job.user, device1.user)
        self.assertEqual(job.group, device1.group)
        self.assertEqual(job.user, device2.user)
        self.assertEqual(job.group, device2.group)
        self.assertEqual(job.is_public, True)
        self.assertEqual(device1.is_public, False)
        # multinode must pass
        job_data = {
            'actions': [
                {
                    'command': 'submit_results',
                    'parameters': {
                        'server': 'http://localhost/RPC2',
                        'stream': b.pathname,
                    }
                }
            ],
            'device_group': [
                {
                    "role": "felix",
                    "count": 1,
                    "device_type": device_type1.name
                },
                {
                    "role": "rex",
                    "count": 1,
                    "device_type": device_type2.name
                }
            ],
        }
        job_data.update({'timeout': 1, 'health_check': False})
        job_json = simplejson.dumps(job_data, sort_keys=True, indent=4 * ' ')
        job = TestJob.from_json_and_user(job_json, user)
        self.assertEqual(len(job), 2)
        self.assertEqual(job[0].is_public, True)
        self.assertEqual(job[1].is_public, True)
        self.factory.cleanup()

    def test_device_type_with_target(self):
        """
        See https://bugs.launchpad.net/lava-server/+bug/1318579
        Check that a submission with device_type and target
        results in the device_type being dropped.
        """
        user = self.factory.make_user()
        group = self.factory.make_group()
        group.user_set.add(user)
        b = BundleStream.objects.create(
            slug='hidden', is_anonymous=False, group=group,
            is_public=True)
        b.save()
        device_type = self.factory.make_device_type('base')
        device = self.factory.make_device(device_type=device_type, hostname="generic")
        job_data = {
            "device_type": "broken",
            "target": device.hostname,
            "timeout": 1,
            "health_check": False,
            'actions': [
                {
                    'command': 'submit_results',
                    'parameters': {
                        'server': 'http://localhost/RPC2',
                        'stream': b.pathname,
                    }
                }
            ],
        }
        job_json = simplejson.dumps(job_data, sort_keys=True, indent=4 * ' ')
        job = TestJob.from_json_and_user(job_json, user)
        self.assertNotIn("device_type", job.definition)
        self.assertIn('device_type', job_data)
        definition_data = simplejson.loads(job.definition)
        self.assertEqual(definition_data['target'], job_data['target'])
        self.assertEqual(definition_data['timeout'], job_data['timeout'])
        self.assertEqual(definition_data['health_check'], job_data['health_check'])
        self.factory.cleanup()

    def test_from_json_and_user_repeat_parameter_expansion(self):
        device_type = self.factory.make_device_type('base')
        device = self.factory.make_device(device_type=device_type, hostname="generic")
        repeat = 5
        job_data = {
            'timeout': 1,
            'target': device.hostname,
            'actions': [
                {
                    'command': 'lava_test_shell',
                    'parameters': {
                        'repeat': repeat,
                        'testdef_repos': [
                            {
                                'git-repo': 'git://server/test.git',
                                'testdef': 'testdef.yaml'
                            }
                        ],
                    }
                }
            ],
        }
        job_json = simplejson.dumps(job_data, sort_keys=True, indent=4 * ' ')
        job = TestJob.from_json_and_user(job_json, self.factory.make_user())
        definition_data = simplejson.loads(job.definition)
        self.assertEqual(len(definition_data['actions']), repeat)
        self.assertEqual(job.status, TestJob.SUBMITTED)
        self.factory.cleanup()

    def test_from_json_and_user_repeat_parameter_replace_with_repeat_count(self):
        device_type = self.factory.make_device_type('base')
        device = self.factory.make_device(device_type=device_type, hostname="generic")
        repeat = 5
        job_data = {
            'timeout': 1,
            'target': device.hostname,
            'actions': [
                {
                    'command': 'lava_test_shell',
                    'parameters': {
                        'repeat': repeat,
                        'testdef_repos': [
                            {
                                'git-repo': 'git://server/test.git',
                                'testdef': 'testdef.yaml'
                            }
                        ],
                    }
                }
            ],
        }
        job_json = simplejson.dumps(job_data, sort_keys=True, indent=4 * ' ')
        job = TestJob.from_json_and_user(job_json, self.factory.make_user())
        definition_data = simplejson.loads(job.definition)
        self.assertEqual(len(definition_data['actions']), repeat)
        for i in range(repeat):
            self.assertEqual(definition_data['actions'][i]['parameters']['repeat_count'], i)
            self.assertNotIn('repeat', definition_data['actions'][i]['parameters'])
        self.assertEqual(job.status, TestJob.SUBMITTED)
        self.factory.cleanup()

    def test_from_json_and_user_repeat_parameter_zero(self):
        device_type = self.factory.make_device_type('base')
        device = self.factory.make_device(device_type=device_type, hostname="generic")
        repeat = 0
        job_data = {
            'timeout': 1,
            'target': device.hostname,
            'actions': [
                {
                    'command': 'lava_test_shell',
                    'parameters': {
                        'repeat': repeat,
                        'testdef_repos': [
                            {
                                'git-repo': 'git://server/test.git',
                                'testdef': 'testdef.yaml'
                            }
                        ],
                    }
                }
            ],
        }
        job_json = simplejson.dumps(job_data, sort_keys=True, indent=4 * ' ')
        job = TestJob.from_json_and_user(job_json, self.factory.make_user())
        definition_data = simplejson.loads(job.definition)
        self.assertEqual(len(definition_data['actions']), 1)
        self.assertNotIn('repeat_count', definition_data['actions'][0]['parameters'])
        self.assertNotIn('repeat', definition_data['actions'][0]['parameters'])
        self.assertEqual(job.status, TestJob.SUBMITTED)
        self.factory.cleanup()

    def test_from_json_and_user_repeat_parameter_not_supported(self):
        device_type = self.factory.make_device_type('base')
        device = self.factory.make_device(device_type=device_type, hostname="generic")
        repeat = 1
        job_data = {
            'timeout': 1,
            'target': device.hostname,
            'actions': [
                {
                    'command': 'deploy_linaro_image',
                    'parameters': {
                        'repeat': repeat,
                        'image': 'file:///pathto/image.img.gz'
                    }
                }
            ],
        }
        job_json = simplejson.dumps(job_data, sort_keys=True, indent=4 * ' ')
        self.assertRaises(
            ValueError, TestJob.from_json_and_user, job_json,
            self.factory.make_user())
        self.factory.cleanup()

    def test_is_deprecated_json(self):
        self.assertTrue(is_deprecated_json(self.factory.make_job_json()))
        self.assertFalse(is_deprecated_json(self.factory.make_job_yaml()))

        invalid_job_data = self.factory.make_invalid_job_json()
        self.assertFalse(is_deprecated_json(invalid_job_data))


class TestHiddenTestJob(TestCaseWithFactory):  # pylint: disable=too-many-ancestors

    def test_hidden_device_type_sets_restricted_device(self):
        device_type = self.factory.make_hidden_device_type('hidden')
        device = self.factory.make_device(device_type=device_type, hostname="hidden1")
        device.save()
        self.assertEqual(device.is_public, False)

    def make_job_json_for_stream_name(self, stream_name, **kw):
        return self.factory.make_job_json(
            actions=[
                {
                    'command': 'submit_results',
                    'parameters': {
                        'server': 'http://localhost/RPC2',
                        'stream': stream_name,
                    }
                }
            ], **kw)

    def test_from_json_and_user_rejects_submit_without_stream(self):
        user = self.factory.make_user()
        device_type = self.factory.make_hidden_device_type('hide_me')
        device = self.factory.make_device(device_type=device_type, hostname="hideme1")
        device.save()
        self.assertEqual(device.is_public, False)
        j = self.factory.make_job_json(target='hidden1')
        self.assertRaises(DevicesUnavailableException, TestJob.from_json_and_user, j, user)

    def test_from_json_and_user_rejects_submit_to_anonmyous(self):
        user = self.factory.make_user()
        anon_user = User.objects.get_or_create(username="anonymous-owner")[0]
        device_type = self.factory.make_hidden_device_type('hide_me_now')
        self.factory.make_device(device_type=device_type, hostname="hidden1")
        b = BundleStream.objects.create(
            slug='anonymous', is_anonymous=True, user=anon_user,
            is_public=True)
        b.save()
        j = self.make_job_json_for_stream_name('/anonymous/anonymous/', target='hidden1')
        self.assertRaises(DevicesUnavailableException, TestJob.from_json_and_user, j, user)

    def test_hidden_submitted_job_is_hidden(self):
        user = self.factory.make_user()
        anon_user = User.objects.get_or_create(username="anonymous-owner")[0]
        device_type = self.factory.make_hidden_device_type('hide_me_now')
        device = self.factory.make_device(device_type=device_type, hostname="hidden1")
        device.user = user
        device.is_public = False
        device.save()
        b = BundleStream.objects.create(
            slug='hidden', is_anonymous=False, user=user,
            is_public=False)
        b.save()
        self.assertEqual(b.is_public, False)
        j = self.make_job_json_for_stream_name('/private/personal/%s/hidden/' % user.username, target='hidden1')
        job = TestJob.from_json_and_user(j, user)
        self.assertEqual(job.user, device.user)
        self.assertEqual(job.is_public, False)
        self.assertEqual(device.is_public, False)
        self.assertRaises(DevicesUnavailableException, TestJob.from_json_and_user, j, anon_user)
