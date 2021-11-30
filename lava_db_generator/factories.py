import factory
import factory.fuzzy

from django.contrib.auth.models import User
from lava_scheduler_app.models import TestJob

from lava_common.decorators import nottest


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = factory.Faker("user_name")


@nottest
class TestJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TestJob

    submitter = factory.fuzzy.FuzzyChoice(User.objects.all())
