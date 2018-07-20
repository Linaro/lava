from django.apps import AppConfig
from django.conf import settings


class LAVASchedulerConfig(AppConfig):
    name = "lava_scheduler_app"
    verbose_name = "lava_scheduler_app"

    def ready(self):
        import lava_scheduler_app.checks
        import lava_scheduler_app.signals
