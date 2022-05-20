import factory
import factory.fuzzy

from datetime import datetime, timedelta, timezone
from random import choice

from django.contrib.auth.models import User, Group
from django.db.models import Q
from lava_scheduler_app.models import DeviceType, Device, TestJob, Worker

from lava_common.decorators import nottest


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Faker("user_name")

    @factory.post_generation
    def number_of_particpated_projects(
        self, create, number_of_particpated_projects: int, **kwargs
    ):
        if not create:
            return

        for _ in range(number_of_particpated_projects):
            self.groups.add(choice(Group.objects.filter(~Q(name="lava-health"))))

    @factory.post_generation
    def set_password_to(self, create, new_password: str, **kwargs):
        if not create:
            return

        self.set_password(new_password)


class GroupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Group
        django_get_or_create = ("name",)

    name = factory.Faker("user_name")


class ProjectGroupFactory(GroupFactory):
    name = factory.Sequence(lambda n: f"project{n}")


class WorkerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Worker
        django_get_or_create = ("hostname",)

    hostname = factory.Faker("hostname", levels=1)


class DeviceTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeviceType
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"devicetype{n}")


class DeviceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Device
        django_get_or_create = ("hostname",)

    hostname = factory.Faker("hostname", levels=0)
    device_type = factory.fuzzy.FuzzyChoice(DeviceType.objects.all())
    worker_host = factory.fuzzy.FuzzyChoice(Worker.objects.all())

    @factory.post_generation
    def create_device_template(self,
                               create,
                               create_device_template: bool = False, **kwrags):
        if (not create) or (not create_device_template):
            return

        from django.conf import settings
        from pathlib import Path

        device_template_dir = Path(settings.DEVICES_PATH)

        with open(device_template_dir / (self.hostname + '.jinja2'), mode='w+t') as f:
            f.write(r"{% " + f"extends '{self.device_type.name}.jinja2'" + r" %}")


@nottest
class TestJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TestJob

    is_public = True
    actual_device = factory.fuzzy.FuzzyChoice(Device.objects.all())
    requested_device_type = factory.fuzzy.FuzzyChoice(DeviceType.objects.all())
    description = "test description"

    end_time = factory.fuzzy.FuzzyDateTime(
        datetime.now(tz=timezone.utc),
        datetime.now(tz=timezone.utc) + timedelta(hours=1),
    )
    start_time = factory.fuzzy.FuzzyDateTime(
        datetime.now(tz=timezone.utc) - timedelta(days=500),
        datetime.now(tz=timezone.utc),
    )

    @factory.post_generation
    def number_of_particpated_projects(
        self, create, number_of_particpated_projects: int, **kwargs
    ):
        if not create:
            return

        for _ in range(number_of_particpated_projects):
            self.viewing_groups.add(choice(Group.objects.all()))
