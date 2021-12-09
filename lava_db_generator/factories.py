import factory
import factory.fuzzy

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


@nottest
class TestJobWithViewingGroupFactory(TestJobFactory):
    @factory.post_generation
    def viewing_groups(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            self.viewing_groups.add(extracted)
