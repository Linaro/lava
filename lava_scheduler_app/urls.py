# Copyright (C) 2011-2019 Linaro Limited
#
# Author: Neil Williams <neil.williams@linaro.org>
#         Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.urls import re_path

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

urlpatterns = [
    re_path(r"^$", index, name="lava.scheduler"),
    re_path(r"^reports$", reports, name="lava.scheduler.reports"),
    re_path(
        r"^reports/failures$", failure_report, name="lava.scheduler.failure_report"
    ),
    re_path(r"^activejobs$", active_jobs, name="lava.scheduler.job.active"),
    re_path(r"^alljobs$", job_list, name="lava.scheduler.job.list"),
    re_path(r"joberrors$", job_errors, name="lava.scheduler.job.errors"),
    re_path(r"^jobsubmit$", job_submit, name="lava.scheduler.job.submit"),
    re_path(r"^device_types$", all_device_types, name="lava.scheduler.device_types"),
    re_path(
        r"^device_type/(?P<pk>[-_a-zA-Z0-9]+)$",
        device_type_detail,
        name="lava.scheduler.device_type.detail",
    ),
    re_path(r"^alldevices$", device_list, name="lava.scheduler.alldevices"),
    re_path(
        r"^device/(?P<pk>[-_a-zA-Z0-9.@]+)$",
        device_detail,
        name="lava.scheduler.device.detail",
    ),
    re_path(
        r"^device/(?P<pk>[-_a-zA-Z0-9.@]+)/devicedict$",
        device_dictionary,
        name="lava.scheduler.device.dictionary",
    ),
    re_path(
        r"^device/(?P<pk>[-_a-zA-Z0-9.@]+)/devicedict/plain$",
        device_dictionary_plain,
        name="lava.scheduler.device.dictionary.plain",
    ),
    re_path(r"^allworkers$", workers, name="lava.scheduler.workers"),
    re_path(
        r"^worker/(?P<pk>[-_a-zA-Z0-9.@]+)$",
        worker_detail,
        name="lava.scheduler.worker.detail",
    ),
    re_path(
        r"^worker/(?P<pk>[-_a-zA-Z0-9.@]+)/health$",
        worker_health,
        name="lava.scheduler.worker.health",
    ),
    re_path(r"^labhealth/$", lab_health, name="lava.scheduler.labhealth"),
    re_path(
        r"^labhealth/device/(?P<pk>[-_a-zA-Z0-9.@]+)$",
        health_job_list,
        name="lava.scheduler.labhealth.detail",
    ),
    re_path(r"^longestjobs$", longest_jobs, name="lava.scheduler.longest_jobs"),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)$",
        job_detail,
        name="lava.scheduler.job.detail",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/definition$",
        job_definition,
        name="lava.scheduler.job.definition",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/definition/plain$",
        job_definition_plain,
        name="lava.scheduler.job.definition.plain",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/description$",
        job_description_yaml,
        name="lava.scheduler.job.description.yaml",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/multinode_definition$",
        multinode_job_definition,
        name="lava.scheduler.job.multinode_definition",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/multinode_definition/plain$",
        multinode_job_definition_plain,
        name="lava.scheduler.job.multinode_definition.plain",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/configuration$",
        job_configuration,
        name="lava.scheduler.job.configuration",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/log_file/plain$",
        job_log_file_plain,
        name="lava.scheduler.job.log_file.plain",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/timing$",
        job_timing,
        name="lava.scheduler.job.timing",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/job_status$",
        job_status,
        name="lava.scheduler.job_status",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/cancel$",
        job_cancel,
        name="lava.scheduler.job.cancel",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/fail$",
        job_fail,
        name="lava.scheduler.job.fail",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/resubmit$",
        job_resubmit,
        name="lava.scheduler.job.resubmit",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/annotate_failure$",
        job_annotate_failure,
        name="lava.scheduler.job.annotate_failure",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/toggle_favorite$",
        job_toggle_favorite,
        name="lava.scheduler.job.toggle_favorite",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/log_pipeline_incremental$",
        job_log_incremental,
        name="lava.scheduler.job.log_incremental",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/job_data$",
        job_fetch_data,
        name="lava.scheduler.job.fetch_data",
    ),
    re_path(r"^myjobs$", myjobs, name="lava.scheduler.myjobs"),
    re_path(r"^myactivejobs$", my_active_jobs, name="lava.scheduler.myjobs.active"),
    re_path(r"^myqueuedjobs$", my_queued_jobs, name="lava.scheduler.myjobs.queued"),
    re_path(r"^myerrorjobs$", my_error_jobs, name="lava.scheduler.myjobs.error"),
    re_path(r"^favorite-jobs$", favorite_jobs, name="lava.scheduler.favorite_jobs"),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+\.[0-9]+)/priority$",
        job_change_priority,
        name="lava.scheduler.job.priority",
    ),
    re_path(
        r"^device/(?P<pk>[-_a-zA-Z0-9.@]+)/health$",
        device_health,
        name="lava.scheduler.device.health",
    ),
    re_path(
        r"^alldevices/active$", active_device_list, name="lava.scheduler.active_devices"
    ),
    re_path(
        r"^alldevices/online$", online_device_list, name="lava.scheduler.online_devices"
    ),
    re_path(
        r"^alldevices/passinghealthchecks$",
        passing_health_checks,
        name="lava.scheduler.passing_health_checks",
    ),
    re_path(
        r"^alldevices/maintenance$",
        maintenance_devices,
        name="lava.scheduler.maintenance_devices",
    ),
    re_path(
        r"^reports/device/(?P<pk>[-_a-zA-Z0-9.@]+)",
        device_reports,
        name="lava.scheduler.device_report",
    ),
    re_path(
        r"^reports/device_type/(?P<pk>[-_a-zA-Z0-9]+)",
        device_type_reports,
        name="lava.scheduler.device_type_report",
    ),
    re_path(r"^mydevices$", mydevice_list, name="lava.scheduler.mydevice_list"),
    re_path(
        r"^username-list-json$",
        username_list_json,
        name="lava.scheduler.username_list_json",
    ),
    re_path(r"^queue$", queue, name="lava.scheduler.queue"),
    re_path(r"^healthcheck$", healthcheck, name="lava.scheduler.healthcheck"),
    re_path(r"^running$", running, name="lava.scheduler.running"),
    re_path(
        r"^dthealthhistory/device_type/(?P<pk>[-_a-zA-Z0-9]+)",
        device_type_health_history_log,
        name="lava.scheduler.device_type_health_history_log",
    ),
    re_path(
        r"^mydevicetypehealthhistory$",
        mydevices_health_history_log,
        name="lava.scheduler.mydevices_health_history_log",
    ),
    re_path(
        r"^devicetypeyaml/(?P<pk>[-_a-zA-Z0-9]+)",
        download_device_type_template,
        name="lava_scheduler_download_device_type_yaml",
    ),
    re_path(
        r"^job/(?P<pk>[0-9]+|[0-9]+.[0-9]+)/similarjobs$",
        similar_jobs,
        name="lava.scheduler.job.similar_jobs",
    ),
    re_path(
        r"internal/v1/jobs/(?P<pk>[0-9]+|[0-9]+.[0-9]+)/$",
        internal_v1_jobs,
        name="lava.scheduler.internal.v1.jobs",
    ),
    re_path(
        r"internal/v1/jobs/(?P<pk>[0-9]+|[0-9]+.[0-9]+)/logs/$",
        internal_v1_jobs_logs,
        name="lava.scheduler.internal.v1.jobs.logs",
    ),
    re_path(
        r"internal/v1/workers/$",
        internal_v1_workers,
        name="lava.scheduler.internal.v1.workers",
    ),
    re_path(
        r"internal/v1/workers/(?P<pk>[-_a-zA-Z0-9.@]+)/$",
        internal_v1_workers,
        name="lava.scheduler.internal.v1.workers",
    ),
]
