# Copyright (C) 2011-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.urls import path, register_converter

from lava_common.converters import JobIdConverter
from lava_scheduler_app.views import (
    active_device_list,
    active_jobs,
    all_device_types,
    device_detail,
    device_dictionary,
    device_dictionary_plain,
    device_health,
    device_list,
    device_reports,
    device_type_detail,
    device_type_health_history_log,
    device_type_reports,
    download_device_type_template,
    failure_report,
    favorite_jobs,
    health_job_list,
    healthcheck,
    index,
    internal_v1_jobs,
    internal_v1_jobs_logs,
    internal_v1_workers,
    job_annotate_failure,
    job_cancel,
    job_change_priority,
    job_configuration,
    job_definition,
    job_definition_plain,
    job_description_yaml,
    job_detail,
    job_errors,
    job_fail,
    job_fetch_data,
    job_list,
    job_log_file_plain,
    job_log_incremental,
    job_resubmit,
    job_status,
    job_submit,
    job_timing,
    job_toggle_favorite,
    lab_health,
    longest_jobs,
    maintenance_devices,
    multinode_job_definition,
    multinode_job_definition_plain,
    my_active_jobs,
    my_error_jobs,
    my_queued_jobs,
    mydevice_list,
    mydevices_health_history_log,
    myjobs,
    online_device_list,
    passing_health_checks,
    queue,
    reports,
    running,
    similar_jobs,
    username_list_json,
    worker_detail,
    worker_health,
    workers,
)

register_converter(JobIdConverter, "job_id")

urlpatterns = (
    path("", index, name="lava.scheduler"),
    path("reports", reports, name="lava.scheduler.reports"),
    path("reports/failures", failure_report, name="lava.scheduler.failure_report"),
    path("activejobs", active_jobs, name="lava.scheduler.job.active"),
    path("alljobs", job_list, name="lava.scheduler.job.list"),
    path("joberrors", job_errors, name="lava.scheduler.job.errors"),
    path("jobsubmit", job_submit, name="lava.scheduler.job.submit"),
    path("device_types", all_device_types, name="lava.scheduler.device_types"),
    path(
        "device_type/<str:pk>",
        device_type_detail,
        name="lava.scheduler.device_type.detail",
    ),
    path("alldevices", device_list, name="lava.scheduler.alldevices"),
    path("device/<str:pk>", device_detail, name="lava.scheduler.device.detail"),
    path(
        "device/<str:pk>/devicedict",
        device_dictionary,
        name="lava.scheduler.device.dictionary",
    ),
    path(
        "device/<str:pk>/devicedict/plain",
        device_dictionary_plain,
        name="lava.scheduler.device.dictionary.plain",
    ),
    path("allworkers", workers, name="lava.scheduler.workers"),
    path("worker/<str:pk>", worker_detail, name="lava.scheduler.worker.detail"),
    path("worker/<str:pk>/health", worker_health, name="lava.scheduler.worker.health"),
    path("labhealth/", lab_health, name="lava.scheduler.labhealth"),
    path(
        "labhealth/device/<str:pk>",
        health_job_list,
        name="lava.scheduler.labhealth.detail",
    ),
    path("longestjobs", longest_jobs, name="lava.scheduler.longest_jobs"),
    path("job/<job_id:pk>", job_detail, name="lava.scheduler.job.detail"),
    path(
        "job/<job_id:pk>/definition",
        job_definition,
        name="lava.scheduler.job.definition",
    ),
    path(
        "job/<job_id:pk>/definition/plain",
        job_definition_plain,
        name="lava.scheduler.job.definition.plain",
    ),
    path(
        "job/<job_id:pk>/description",
        job_description_yaml,
        name="lava.scheduler.job.description.yaml",
    ),
    path(
        "job/<job_id:pk>/multinode_definition",
        multinode_job_definition,
        name="lava.scheduler.job.multinode_definition",
    ),
    path(
        "job/<job_id:pk>/multinode_definition/plain",
        multinode_job_definition_plain,
        name="lava.scheduler.job.multinode_definition.plain",
    ),
    path(
        "job/<job_id:pk>/configuration",
        job_configuration,
        name="lava.scheduler.job.configuration",
    ),
    path(
        "job/<job_id:pk>/log_file/plain",
        job_log_file_plain,
        name="lava.scheduler.job.log_file.plain",
    ),
    path("job/<job_id:pk>/timing", job_timing, name="lava.scheduler.job.timing"),
    path("job/<job_id:pk>/job_status", job_status, name="lava.scheduler.job_status"),
    path("job/<job_id:pk>/cancel", job_cancel, name="lava.scheduler.job.cancel"),
    path("job/<job_id:pk>/fail", job_fail, name="lava.scheduler.job.fail"),
    path("job/<job_id:pk>/resubmit", job_resubmit, name="lava.scheduler.job.resubmit"),
    path(
        "job/<job_id:pk>/annotate_failure",
        job_annotate_failure,
        name="lava.scheduler.job.annotate_failure",
    ),
    path(
        "job/<job_id:pk>/toggle_favorite",
        job_toggle_favorite,
        name="lava.scheduler.job.toggle_favorite",
    ),
    path(
        "job/<job_id:pk>/log_pipeline_incremental",
        job_log_incremental,
        name="lava.scheduler.job.log_incremental",
    ),
    path(
        "job/<job_id:pk>/job_data", job_fetch_data, name="lava.scheduler.job.fetch_data"
    ),
    path("myjobs", myjobs, name="lava.scheduler.myjobs"),
    path("myactivejobs", my_active_jobs, name="lava.scheduler.myjobs.active"),
    path("myqueuedjobs", my_queued_jobs, name="lava.scheduler.myjobs.queued"),
    path("myerrorjobs", my_error_jobs, name="lava.scheduler.myjobs.error"),
    path("favorite-jobs", favorite_jobs, name="lava.scheduler.favorite_jobs"),
    path(
        "job/<job_id:pk>/priority",
        job_change_priority,
        name="lava.scheduler.job.priority",
    ),
    path("device/<str:pk>/health", device_health, name="lava.scheduler.device.health"),
    path("alldevices/active", active_device_list, name="lava.scheduler.active_devices"),
    path("alldevices/online", online_device_list, name="lava.scheduler.online_devices"),
    path(
        "alldevices/passinghealthchecks",
        passing_health_checks,
        name="lava.scheduler.passing_health_checks",
    ),
    path(
        "alldevices/maintenance",
        maintenance_devices,
        name="lava.scheduler.maintenance_devices",
    ),
    path(
        "reports/device/<str:pk>", device_reports, name="lava.scheduler.device_report"
    ),
    path(
        "reports/device_type/<str:pk>",
        device_type_reports,
        name="lava.scheduler.device_type_report",
    ),
    path("mydevices", mydevice_list, name="lava.scheduler.mydevice_list"),
    path(
        "username-list-json",
        username_list_json,
        name="lava.scheduler.username_list_json",
    ),
    path("queue", queue, name="lava.scheduler.queue"),
    path("healthcheck", healthcheck, name="lava.scheduler.healthcheck"),
    path("running", running, name="lava.scheduler.running"),
    path(
        "dthealthhistory/device_type/<str:pk>",
        device_type_health_history_log,
        name="lava.scheduler.device_type_health_history_log",
    ),
    path(
        "mydevicetypehealthhistory",
        mydevices_health_history_log,
        name="lava.scheduler.mydevices_health_history_log",
    ),
    path(
        "devicetypeyaml/<str:pk>",
        download_device_type_template,
        name="lava_scheduler_download_device_type_yaml",
    ),
    path(
        "job/<job_id:pk>/similarjobs",
        similar_jobs,
        name="lava.scheduler.job.similar_jobs",
    ),
    path(
        "internal/v1/jobs/<int:pk>/",  # No support for multinode jobs
        internal_v1_jobs,
        name="lava.scheduler.internal.v1.jobs",
    ),
    path(
        "internal/v1/jobs/<int:pk>/logs/",  # No support for multinode jobs
        internal_v1_jobs_logs,
        name="lava.scheduler.internal.v1.jobs.logs",
    ),
    path(
        "internal/v1/workers/",
        internal_v1_workers,
        name="lava.scheduler.internal.v1.workers",
    ),
    path(
        "internal/v1/workers/<str:pk>/",
        internal_v1_workers,
        name="lava.scheduler.internal.v1.workers",
    ),
)
