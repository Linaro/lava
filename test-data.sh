#!/bin/sh
# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: GPL-2.0-or-later

# HACK: seed dummy data for testing the web UI.
#
# Creates an admin user, a qemu device and a few test jobs with realistic
# log output and results, so that the job, device and results pages can be
# inspected in a browser. test.sh mounts this script into the lava-server
# container at /root/entrypoint.d/90-test-data.sh; the entrypoint runs it
# after the database migrations.

set -e

echo "Seeding dummy test data"

# No `|| true`: a failed add is a real signal — the dev container DB is rebuilt
# fresh by the entrypoint, so a failed add means the seed environment is broken.
lava-server manage device-types add qemu
lava-server manage workers add worker01
lava-server manage devices add --device-type qemu --worker worker01 qemu-01

python_code=$(cat <<'PYEOF'
import json
import pathlib
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from lava_results_app.models import TestCase, TestSuite
from lava_scheduler_app.models import Device, DeviceType, TestJob

user, created = User.objects.get_or_create(
    username="admin", defaults={"is_staff": True, "is_superuser": True}
)
if created:
    user.set_password("admin")
    user.save()

dt = DeviceType.objects.get(name="qemu")
device = Device.objects.get(hostname="qemu-01")
device.health = Device.HEALTH_GOOD
device.save()

DEFINITION = """\
device_type: qemu
job_name: qemu smoke tests
timeouts:
  job:
    minutes: 15
  action:
    minutes: 5
priority: medium
visibility: public
context:
  arch: amd64
actions:
- deploy:
    timeout:
      minutes: 5
    to: tmpfs
    images:
      rootfs:
        image_arg: -drive format=raw,file={rootfs}
        url: https://example.com/images/rootfs.img.gz
        compression: gz
- boot:
    timeout:
      minutes: 2
    method: qemu
    media: tmpfs
    prompts:
    - 'root@debian:'
    auto_login:
      login_prompt: 'login:'
      username: root
- test:
    timeout:
      minutes: 5
    definitions:
    - repository: https://git.lavasoftware.org/lava/functional-tests
      from: git
      path: smoke-tests-basic.yaml
      name: smoke-tests
"""


def write_log(job, entries):
    now = timezone.now()
    lines = []
    seconds = 0.0
    for delta, lvl, msg in entries:
        seconds += delta
        stamp = now + timedelta(seconds=seconds)
        lines.append(
            "- " + json.dumps({"dt": stamp.isoformat(), "lvl": lvl, "msg": msg})
        )
    outdir = pathlib.Path(job.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "output.yaml").write_text("\n".join(lines) + "\n")


def result(definition, case, res, **kwargs):
    msg = {"definition": definition, "case": case, "result": res}
    msg.update(kwargs)
    return "results", msg


COMPLETE_LOG = [
    (0.0, "info", "lava-dispatcher, installed at version: 2025.04"),
    (0.1, "info", "start: 0 validate"),
    (0.1, "debug", "Validating that https://example.com/images/rootfs.img.gz exists"),
    (0.3, "info", "validate duration: 0.30"),
    (0.0, *result("lava", "validate", "pass")),
    (0.1, "info", "start: 1 deployimages (timeout 00:05:00) [common]"),
    (0.1, "debug", "downloading https://example.com/images/rootfs.img.gz"),
    (0.5, "debug", "progress   9MB (10%)"),
    (2.0, "debug", "progress  93MB (100%)"),
    (0.2, "info", "deployimages duration: 2.80"),
    (0.0, *result("lava", "deployimages", "pass", duration="2.80")),
    (0.1, "info", "start: 2 boot-image-retry (timeout 00:02:00) [common]"),
    (0.1, "info", "start: 2.1 boot-qemu-image (timeout 00:02:00) [common]"),
    (0.1, "debug", "qemu-system-x86_64 -cpu host -enable-kvm -nographic -drive format=raw,file=/var/lib/lava/dispatcher/tmp/rootfs.img -m 1024"),
    (0.5, "target", "[    0.000000] Linux version 6.1.0-18-amd64 (debian-kernel@lists.debian.org)"),
    (0.2, "target", "[    0.004000] Command line: root=/dev/sda1 ro console=ttyS0"),
    (0.6, "target", "[    1.377254] Run /sbin/init as init process"),
    (1.2, "target", "[  OK  ] Reached target multi-user.target - Multi-User System."),
    (0.4, "target", "debian login:"),
    (0.1, "input", "root"),
    (0.3, "target", "root@debian:~#"),
    (0.1, "info", "auto-login-action duration: 3.40"),
    (0.0, *result("lava", "auto-login-action", "pass", duration="3.40")),
    (0.1, "info", "boot-qemu-image duration: 3.60"),
    (0.0, *result("lava", "boot-qemu-image", "pass", duration="3.60")),
    (0.1, "info", "start: 3 lava-test-retry (timeout 00:05:00) [common]"),
    (0.1, "info", "start: 3.1 lava-test-shell (timeout 00:05:00) [common]"),
    (0.3, "target", "Test shell timeout: 300 seconds"),
    (0.2, "target", "<LAVA_SIGNAL_STARTRUN 0_smoke-tests>"),
    (0.3, "target", "linux-linaro-ubuntu-pwd: pass"),
    (0.0, *result("0_smoke-tests", "linux-linaro-ubuntu-pwd", "pass")),
    (0.2, "target", "linux-linaro-ubuntu-uname: pass"),
    (0.0, *result("0_smoke-tests", "linux-linaro-ubuntu-uname", "pass")),
    (0.2, "target", "linux-linaro-ubuntu-vmstat: pass"),
    (0.0, *result("0_smoke-tests", "linux-linaro-ubuntu-vmstat", "pass")),
    (0.2, "warning", "flaky network detected, retrying wget"),
    (0.8, "target", "linux-linaro-ubuntu-wget: fail"),
    (0.0, *result("0_smoke-tests", "linux-linaro-ubuntu-wget", "fail")),
    (0.2, "target", "<LAVA_SIGNAL_ENDRUN 0_smoke-tests>"),
    (0.1, "info", "lava-test-shell duration: 2.60"),
    (0.0, *result("lava", "lava-test-shell", "pass", duration="2.60")),
    (0.1, "info", "start: 4 finalize (timeout 00:05:00) [common]"),
    (0.2, "target", "reboot: Power down"),
    (0.2, "info", "finalize duration: 0.40"),
    (0.0, *result("lava", "finalize", "pass", duration="0.40")),
    (0.0, *result("lava", "job", "pass")),
]

FAILED_LOG = [
    (0.0, "info", "lava-dispatcher, installed at version: 2025.04"),
    (0.1, "info", "start: 0 validate"),
    (0.3, "info", "validate duration: 0.30"),
    (0.0, *result("lava", "validate", "pass")),
    (0.1, "info", "start: 1 deployimages (timeout 00:05:00) [common]"),
    (0.1, "debug", "downloading https://example.com/images/rootfs.img.gz"),
    (1.0, "debug", "progress  93MB (100%)"),
    (0.2, "info", "deployimages duration: 1.30"),
    (0.0, *result("lava", "deployimages", "pass", duration="1.30")),
    (0.1, "info", "start: 2 boot-image-retry (timeout 00:02:00) [common]"),
    (0.5, "target", "[    0.000000] Linux version 6.1.0-18-amd64"),
    (2.0, "target", "[    4.522011] Kernel panic - not syncing: VFS: Unable to mount root fs"),
    (118.0, "error", "boot-qemu-image timed out after 120 seconds"),
    (0.1, "exception", "JobError: boot-qemu-image timed out"),
    (0.0, *result("lava", "boot-qemu-image", "fail")),
    (0.1, "info", "start: 4 finalize (timeout 00:05:00) [common]"),
    (0.2, "info", "finalize duration: 0.20"),
    (0.0, *result("lava", "job", "fail")),
]


def add_results(job, suite_name, cases):
    suite, _ = TestSuite.objects.get_or_create(job=job, name=suite_name)
    for name, res, duration in cases:
        TestCase.objects.create(
            name=name,
            suite=suite,
            result=res,
            measurement=duration,
            units="seconds" if duration else "",
        )


now = timezone.now()

if not TestJob.objects.filter(description="qemu smoke tests").exists():
    job = TestJob.objects.create(
        description="qemu smoke tests",
        definition=DEFINITION,
        original_definition=DEFINITION,
        submitter=user,
        requested_device_type=dt,
        actual_device=device,
        state=TestJob.STATE_FINISHED,
        health=TestJob.HEALTH_COMPLETE,
        is_public=True,
        start_time=now - timedelta(minutes=9),
        end_time=now - timedelta(minutes=1),
    )
    write_log(job, COMPLETE_LOG)
    add_results(
        job,
        "lava",
        [
            ("validate", TestCase.RESULT_PASS, 0.30),
            ("deployimages", TestCase.RESULT_PASS, 2.80),
            ("auto-login-action", TestCase.RESULT_PASS, 3.40),
            ("boot-qemu-image", TestCase.RESULT_PASS, 3.60),
            ("lava-test-shell", TestCase.RESULT_PASS, 2.60),
            ("finalize", TestCase.RESULT_PASS, 0.40),
            ("job", TestCase.RESULT_PASS, None),
        ],
    )
    add_results(
        job,
        "0_smoke-tests",
        [
            ("linux-linaro-ubuntu-pwd", TestCase.RESULT_PASS, None),
            ("linux-linaro-ubuntu-uname", TestCase.RESULT_PASS, None),
            ("linux-linaro-ubuntu-vmstat", TestCase.RESULT_PASS, None),
            ("linux-linaro-ubuntu-wget", TestCase.RESULT_FAIL, None),
        ],
    )
    print("Created job %d: qemu smoke tests (complete)" % job.id)

if not TestJob.objects.filter(description="qemu boot failure").exists():
    job = TestJob.objects.create(
        description="qemu boot failure",
        definition=DEFINITION,
        original_definition=DEFINITION,
        submitter=user,
        requested_device_type=dt,
        actual_device=device,
        state=TestJob.STATE_FINISHED,
        health=TestJob.HEALTH_INCOMPLETE,
        failure_comment="boot-qemu-image timed out: kernel panic while mounting rootfs",
        is_public=True,
        start_time=now - timedelta(minutes=30),
        end_time=now - timedelta(minutes=27),
    )
    write_log(job, FAILED_LOG)
    add_results(
        job,
        "lava",
        [
            ("validate", TestCase.RESULT_PASS, 0.30),
            ("deployimages", TestCase.RESULT_PASS, 1.30),
            ("boot-qemu-image", TestCase.RESULT_FAIL, None),
            ("job", TestCase.RESULT_FAIL, None),
        ],
    )
    print("Created job %d: qemu boot failure (incomplete)" % job.id)

if not TestJob.objects.filter(description="qemu queued job").exists():
    job = TestJob.objects.create(
        description="qemu queued job",
        definition=DEFINITION,
        original_definition=DEFINITION,
        submitter=user,
        requested_device_type=dt,
        state=TestJob.STATE_SUBMITTED,
        is_public=True,
    )
    print("Created job %d: qemu queued job (submitted)" % job.id)
PYEOF
)
lava-server manage shell -c "$python_code"

# The entrypoint checks that all media files belong to lavaserver
chown -R lavaserver:lavaserver /var/lib/lava-server/default/media/job-output

echo "Dummy data ready: sign in with admin/admin"
