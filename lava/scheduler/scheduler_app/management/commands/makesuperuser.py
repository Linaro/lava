from django.core.management.base import LabelCommand

from django.contrib.auth.models import User

class Command(LabelCommand):
    help = 'Make the listed users into superusers.'

    def handle_label(self, username, **options):
        u = User.objects.get(username=username)
        u.is_staff = True
        u.is_active = True
        u.is_superuser = True
        u.save()
