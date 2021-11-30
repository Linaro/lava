import factory
import factory.fuzzy

import random

from django.contrib.auth.models import User, Group
from lava_scheduler_app.models import TestJob

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


@nottest
class TestJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TestJob

    submitter = factory.fuzzy.FuzzyChoice(User.objects.all())

    @factory.post_generation
    def viewing_groups(self, create, _, **kwargs):
        if not create:
            return

        project_ratios = kwargs["project_ratios"]
        project_groups = Group.objects.filter(name__istartswith="project")
        project_groups = project_groups[: len(project_ratios)]

        if random.random() < kwargs["project_group_ratio"]:
            self.viewing_groups.add(random.choices(project_groups, project_ratios)[0])
