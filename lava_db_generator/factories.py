import factory
import factory.fuzzy

from datetime import datetime, timedelta, timezone

from django.contrib.auth.models import User, Group
from lava_scheduler_app.models import DeviceType, Device, TestJob

from lava_common.decorators import nottest


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Faker("user_name")


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ("name",)

    name = factory.Faker("user_name")


class ProjectGroupFactory(GroupFactory):
    name = factory.Sequence(lambda n: f"project{n}")


class DeviceTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeviceType
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"devicetype{n}")


class DeviceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Device
        django_get_or_create = ("hostname",)

    hostname = factory.Sequence(lambda n: f"device{n}")
    device_type = factory.fuzzy.FuzzyChoice(DeviceType.objects.all())


@nottest
class TestJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TestJob

    is_public = True
    submitter = factory.fuzzy.FuzzyChoice(User.objects.all())


@nottest
class TestJobWithActualDevice(TestJobFactory):
    actual_device = factory.fuzzy.FuzzyChoice(Device.objects.all())
    requested_device_type = factory.fuzzy.FuzzyChoice(DeviceType.objects.all())
    description = "test description"

    end_time = factory.fuzzy.FuzzyDateTime(
        datetime.now(tz=timezone.utc),
        datetime.now(tz=timezone.utc) + timedelta(hours=1),
    )
    start_time = factory.fuzzy.FuzzyDateTime(
        datetime.now(tz=timezone.utc) - timedelta(hours=5),
        datetime.now(tz=timezone.utc),
    )

    @factory.post_generation
    def viewing_groups(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            self.is_public = False
            self.viewing_groups.add(extracted)
