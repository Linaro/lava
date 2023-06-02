import django.db.models.deletion
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, connections, migrations, models
from django.db.migrations.recorder import MigrationRecorder

connection = connections[DEFAULT_DB_ALIAS]
recorder = MigrationRecorder(connection)
linaro_django_xmlrpc_applied = False
lava_scheduler_app_applied = False
for app, name in recorder.applied_migrations():
    if app == "linaro_django_xmlrpc" and name == "0001_initial":
        linaro_django_xmlrpc_applied = True
    if app == "lava_scheduler_app" and name == "0001_initial":
        lava_scheduler_app_applied = True
if not linaro_django_xmlrpc_applied and lava_scheduler_app_applied:
    recorder.record_applied("linaro_django_xmlrpc", "0001_initial")


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("linaro_django_xmlrpc", "__first__"),
    ]

    operations = [
        migrations.CreateModel(
            name="DefaultDeviceOwner",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "default_owner",
                    models.BooleanField(
                        default=False,
                        unique=True,
                        verbose_name="Default owner of unrestricted devices",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Device",
            fields=[
                ("is_public", models.BooleanField(default=False)),
                (
                    "hostname",
                    models.CharField(
                        max_length=200,
                        serialize=False,
                        verbose_name="Hostname",
                        primary_key=True,
                    ),
                ),
                (
                    "device_version",
                    models.CharField(
                        default=None,
                        max_length=200,
                        null=True,
                        verbose_name="Device Version",
                        blank=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        default=None,
                        max_length=200,
                        null=True,
                        verbose_name="Device Description",
                        blank=True,
                    ),
                ),
                (
                    "status",
                    models.IntegerField(
                        default=1,
                        verbose_name="Device status",
                        choices=[
                            (0, "Offline"),
                            (1, "Idle"),
                            (2, "Running"),
                            (3, "Going offline"),
                            (4, "Retired"),
                            (5, "Reserved"),
                        ],
                    ),
                ),
                (
                    "health_status",
                    models.IntegerField(
                        default=0,
                        verbose_name="Device Health",
                        choices=[
                            (0, "Unknown"),
                            (1, "Pass"),
                            (2, "Fail"),
                            (3, "Looping"),
                        ],
                    ),
                ),
            ],
            options={"abstract": False},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="DeviceStateTransition",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                (
                    "old_state",
                    models.IntegerField(
                        choices=[
                            (0, "Offline"),
                            (1, "Idle"),
                            (2, "Running"),
                            (3, "Going offline"),
                            (4, "Retired"),
                            (5, "Reserved"),
                        ]
                    ),
                ),
                (
                    "new_state",
                    models.IntegerField(
                        choices=[
                            (0, "Offline"),
                            (1, "Idle"),
                            (2, "Running"),
                            (3, "Going offline"),
                            (4, "Retired"),
                            (5, "Reserved"),
                        ]
                    ),
                ),
                ("message", models.TextField(null=True, blank=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        blank=True,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="DeviceType",
            fields=[
                ("name", models.SlugField(serialize=False, primary_key=True)),
                (
                    "health_check_job",
                    models.TextField(default=None, null=True, blank=True),
                ),
                (
                    "display",
                    models.BooleanField(
                        default=True,
                        help_text="Should this be displayed in the GUI or not. This can be useful if you are removing all devices of this type but don't want to loose the test results generated by the devices.",
                    ),
                ),
                (
                    "owners_only",
                    models.BooleanField(
                        default=False,
                        help_text="Hide this device type for all users except owners of devices of this type.",
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="JobFailureTag",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(unique=True, max_length=256)),
                ("description", models.TextField(null=True, blank=True)),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.SlugField(unique=True)),
                ("description", models.TextField(null=True, blank=True)),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="TemporaryDevice",
            fields=[
                (
                    "device_ptr",
                    models.OneToOneField(
                        parent_link=True,
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        to="lava_scheduler_app.Device",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "vm_group",
                    models.CharField(
                        default=None,
                        max_length=64,
                        null=True,
                        verbose_name="VM Group",
                        blank=True,
                    ),
                ),
            ],
            options={},
            bases=("lava_scheduler_app.device",),
        ),
        migrations.CreateModel(
            name="TestJob",
            fields=[
                ("is_public", models.BooleanField(default=False)),
                ("id", models.AutoField(serialize=False, primary_key=True)),
                (
                    "sub_id",
                    models.CharField(max_length=200, verbose_name="Sub ID", blank=True),
                ),
                (
                    "target_group",
                    models.CharField(
                        default=None,
                        max_length=64,
                        null=True,
                        verbose_name="Target Group",
                        blank=True,
                    ),
                ),
                (
                    "vm_group",
                    models.CharField(
                        default=None,
                        max_length=64,
                        null=True,
                        verbose_name="VM Group",
                        blank=True,
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        default=None,
                        max_length=200,
                        null=True,
                        verbose_name="Description",
                        blank=True,
                    ),
                ),
                ("health_check", models.BooleanField(default=False)),
                (
                    "submit_time",
                    models.DateTimeField(auto_now_add=True, verbose_name="Submit time"),
                ),
                (
                    "start_time",
                    models.DateTimeField(
                        verbose_name="Start time", null=True, editable=False, blank=True
                    ),
                ),
                (
                    "end_time",
                    models.DateTimeField(
                        verbose_name="End time", null=True, editable=False, blank=True
                    ),
                ),
                (
                    "status",
                    models.IntegerField(
                        default=0,
                        verbose_name="Status",
                        choices=[
                            (0, "Submitted"),
                            (1, "Running"),
                            (2, "Complete"),
                            (3, "Incomplete"),
                            (4, "Canceled"),
                            (5, "Canceling"),
                        ],
                    ),
                ),
                (
                    "priority",
                    models.IntegerField(
                        default=50,
                        verbose_name="Priority",
                        choices=[(0, "Low"), (50, "Medium"), (100, "High")],
                    ),
                ),
                ("definition", models.TextField(editable=False)),
                ("original_definition", models.TextField(editable=False, blank=True)),
                ("multinode_definition", models.TextField(editable=False, blank=True)),
                ("vmgroup_definition", models.TextField(editable=False, blank=True)),
                ("admin_notifications", models.TextField(editable=False, blank=True)),
                (
                    "log_file",
                    models.FileField(
                        default=None, null=True, upload_to="lava-logs", blank=True
                    ),
                ),
                ("failure_comment", models.TextField(null=True, blank=True)),
                (
                    "_results_link",
                    models.CharField(
                        default=None,
                        max_length=400,
                        null=True,
                        db_column="results_link",
                        blank=True,
                    ),
                ),
                (
                    "actual_device",
                    models.ForeignKey(
                        related_name="+",
                        default=None,
                        blank=True,
                        to="lava_scheduler_app.Device",
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "failure_tags",
                    models.ManyToManyField(
                        related_name="failure_tags",
                        to="lava_scheduler_app.JobFailureTag",
                        blank=True,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        blank=True, to="auth.Group", null=True, on_delete=models.CASCADE
                    ),
                ),
                (
                    "requested_device",
                    models.ForeignKey(
                        related_name="+",
                        default=None,
                        blank=True,
                        to="lava_scheduler_app.Device",
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "requested_device_type",
                    models.ForeignKey(
                        related_name="+",
                        default=None,
                        blank=True,
                        to="lava_scheduler_app.DeviceType",
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "submit_token",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        blank=True,
                        to="linaro_django_xmlrpc.AuthToken",
                        null=True,
                    ),
                ),
                (
                    "submitter",
                    models.ForeignKey(
                        related_name="+",
                        verbose_name="Submitter",
                        to=settings.AUTH_USER_MODEL,
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "tags",
                    models.ManyToManyField(to="lava_scheduler_app.Tag", blank=True),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={"abstract": False},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="TestJobUser",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "is_favorite",
                    models.BooleanField(default=False, verbose_name="Favorite job"),
                ),
                (
                    "test_job",
                    models.ForeignKey(
                        to="lava_scheduler_app.TestJob", on_delete=models.CASCADE
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="Worker",
            fields=[
                (
                    "hostname",
                    models.CharField(
                        primary_key=True,
                        default=None,
                        serialize=False,
                        editable=False,
                        max_length=200,
                        verbose_name="Hostname",
                    ),
                ),
                (
                    "rpc2_url",
                    models.CharField(
                        default=None,
                        max_length=200,
                        blank=True,
                        help_text="Corresponds to the master node's RPC2 url. Does not have any impact when set on a worker node.",
                        null=True,
                        verbose_name="Master RPC2 URL",
                    ),
                ),
                (
                    "display",
                    models.BooleanField(
                        default=True,
                        help_text="Should this be displayed in the GUI or not. This will be useful when a worker needs to be removed but still linked device status transitions and devices should be intact.",
                    ),
                ),
                (
                    "ip_address",
                    models.CharField(
                        default=None,
                        editable=False,
                        max_length=20,
                        blank=True,
                        null=True,
                        verbose_name="IP Address",
                    ),
                ),
                (
                    "is_master",
                    models.BooleanField(default=False, verbose_name="Is Master?"),
                ),
                (
                    "description",
                    models.TextField(
                        default=None,
                        max_length=200,
                        null=True,
                        verbose_name="Worker Description",
                        blank=True,
                    ),
                ),
                (
                    "uptime",
                    models.CharField(
                        default=None,
                        editable=False,
                        max_length=200,
                        blank=True,
                        null=True,
                        verbose_name="Host Uptime",
                    ),
                ),
                (
                    "arch",
                    models.CharField(
                        default=None,
                        editable=False,
                        max_length=200,
                        blank=True,
                        null=True,
                        verbose_name="Architecture",
                    ),
                ),
                (
                    "platform",
                    models.CharField(
                        default=None,
                        editable=False,
                        max_length=200,
                        blank=True,
                        null=True,
                        verbose_name="Platform",
                    ),
                ),
                (
                    "hardware_info",
                    models.TextField(
                        verbose_name="Complete Hardware Information",
                        editable=False,
                        blank=True,
                    ),
                ),
                (
                    "software_info",
                    models.TextField(
                        verbose_name="Complete Software Information",
                        editable=False,
                        blank=True,
                    ),
                ),
                (
                    "last_heartbeat",
                    models.DateTimeField(
                        verbose_name="Last Heartbeat",
                        null=True,
                        editable=False,
                        blank=True,
                    ),
                ),
                (
                    "last_master_scheduler_tick",
                    models.DateTimeField(
                        help_text="Corresponds to the master node's last scheduler tick. Does not have any impact when set on a worker node.",
                        verbose_name="Last Master Scheduler Tick",
                        null=True,
                        editable=False,
                        blank=True,
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name="testjobuser", unique_together={("test_job", "user")}
        ),
        migrations.AddField(
            model_name="devicestatetransition",
            name="device",
            field=models.ForeignKey(
                related_name="transitions",
                to="lava_scheduler_app.Device",
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="devicestatetransition",
            name="job",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_NULL,
                blank=True,
                to="lava_scheduler_app.TestJob",
                null=True,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="current_job",
            field=models.ForeignKey(
                related_name="+",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                blank=True,
                to="lava_scheduler_app.TestJob",
                unique=True,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="device_type",
            field=models.ForeignKey(
                verbose_name="Device type",
                to="lava_scheduler_app.DeviceType",
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="group",
            field=models.ForeignKey(
                blank=True, to="auth.Group", null=True, on_delete=models.CASCADE
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="last_health_report_job",
            field=models.ForeignKey(
                related_name="+",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                blank=True,
                to="lava_scheduler_app.TestJob",
                unique=True,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="physical_group",
            field=models.ForeignKey(
                related_name="physical-group",
                default=None,
                blank=True,
                to="auth.Group",
                null=True,
                verbose_name="Group with physical access",
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="physical_owner",
            field=models.ForeignKey(
                related_name="physical-owner",
                default=None,
                blank=True,
                to=settings.AUTH_USER_MODEL,
                null=True,
                verbose_name="User with physical access",
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="tags",
            field=models.ManyToManyField(to="lava_scheduler_app.Tag", blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="user",
            field=models.ForeignKey(
                blank=True,
                to=settings.AUTH_USER_MODEL,
                null=True,
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="device",
            name="worker_host",
            field=models.ForeignKey(
                default=None,
                blank=True,
                to="lava_scheduler_app.Worker",
                null=True,
                verbose_name="Worker Host",
                on_delete=models.CASCADE,
            ),
            preserve_default=True,
        ),
    ]
