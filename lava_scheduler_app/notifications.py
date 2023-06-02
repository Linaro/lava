# Copyright (C) 2019 Linaro Limited
#
# Author: Remi Duraffort <remi.duraffort@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import contextlib
import logging
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.db import IntegrityError
from django.db.models import Q
from django.urls import reverse

from lava_results_app.models import Query, TestCase, TestSuite
from lava_scheduler_app import dbutils, utils
from lava_scheduler_app.models import (
    Notification,
    NotificationCallback,
    NotificationRecipient,
    TestJob,
)
from linaro_django_xmlrpc.models import AuthToken


def get_token_from_description(user, description):
    tokens = AuthToken.objects.filter(user=user, description=description)
    if tokens:
        return tokens.first().secret
    return description


def get_query_results(notification):
    if notification.query_name:
        query = Query.objects.get(
            name=notification.query_name, owner=notification.query_owner
        )
        # We use query_owner as user here since we show only status.
        return query.get_results(notification.query_owner)[: notification.QUERY_LIMIT]
    else:
        return Query.get_queryset(
            notification.entity,
            Query.parse_conditions(notification.entity, notification.conditions),
            notification.QUERY_LIMIT,
        )


def get_query_link(notification):
    if notification.query_name:
        query = Query.objects.get(
            name=notification.query_name, owner=notification.query_owner
        )
        return query.get_absolute_url()
    else:
        # Make absolute URL manually.
        return "%s?entity=%s&conditions=%s" % (
            reverse("lava.results.query_custom"),
            notification.entity.model,
            notification.conditions,
        )


def substitute_callback_url_variables(job, callback_url):
    # Substitute variables in callback_url with field values from job.
    # Format: { FIELD_NAME }
    # If field name is non-existing, return None.
    logger = logging.getLogger("lava-scheduler")

    for sub in re.findall(r"{\s*[A-Z_-]*\s*}", callback_url):
        attribute_name = sub.replace("{", "").replace("}", "").strip().lower()
        # FIXME: Keep legacy behavior. Should be removed.
        if attribute_name == "status":
            attr = job.get_legacy_status()
        elif attribute_name == "status_string":
            attr = job.get_legacy_status_display().lower()
        else:
            try:
                attr = getattr(job, attribute_name)
            except AttributeError:
                logger.error(
                    "Attribute '%s' does not exist in TestJob.", attribute_name
                )
                continue
        callback_url = callback_url.replace(str(sub), str(attr))

    return callback_url


def create_callback(job, callback_data, notification):
    notification_callback = NotificationCallback(notification=notification)

    notification_callback.url = substitute_callback_url_variables(
        job, callback_data["url"]
    )
    if callback_data.get("token"):
        notification_callback.token = get_token_from_description(
            job.submitter, callback_data["token"]
        )
        notification_callback.header = callback_data.get("header", "Authorization")
    notification_callback.method = NotificationCallback.METHOD_MAP[
        callback_data.get("method", "GET")
    ]
    notification_callback.dataset = NotificationCallback.DATASET_MAP[
        callback_data.get("dataset", "minimal")
    ]
    notification_callback.content_type = NotificationCallback.CONTENT_TYPE_MAP[
        callback_data.get("content-type", "urlencoded")
    ]

    notification_callback.save()


def get_notification_args(job):
    args = {}
    args["job"] = job
    args["url_prefix"] = "http://%s" % dbutils.get_domain()
    # Get lava.job result if available
    with contextlib.suppress(TestCase.DoesNotExist):
        lava_job_obj = TestCase.objects.get(
            suite__job=job, suite__name="lava", name="job"
        )
        args["lava_job_result"] = lava_job_obj.action_metadata

    args["query"] = {}
    if job.notification.query_name or job.notification.entity:
        args["query"]["results"] = get_query_results(job.notification)
        args["query"]["link"] = get_query_link(job.notification)
        # Find the first job which has health HEALTH_COMPLETE and is not the
        # current job (this can happen with custom queries) for comparison.
        compare_index = None
        for index, result in enumerate(args["query"]["results"]):
            if result.health == TestJob.HEALTH_COMPLETE and job != result:
                compare_index = index
                break

        args["query"]["compare_index"] = compare_index
        if compare_index is not None and job.notification.blacklist:
            # Get testsuites diffs between current job and latest complete
            # job from query.
            new_suites = job.testsuite_set.all().exclude(
                name__in=job.notification.blacklist
            )
            old_suites = (
                args["query"]["results"][compare_index]
                .testsuite_set.all()
                .exclude(name__in=job.notification.blacklist)
            )
            left_suites_diff = new_suites.exclude(
                name__in=old_suites.values_list("name", flat=True)
            )
            right_suites_diff = old_suites.exclude(
                name__in=new_suites.values_list("name", flat=True)
            )

            args["query"]["left_suites_diff"] = left_suites_diff
            args["query"]["right_suites_diff"] = right_suites_diff

            # Get testcases diffs between current job and latest complete
            # job from query.
            new_cases = (
                TestCase.objects.filter(suite__job=job)
                .exclude(name__in=job.notification.blacklist)
                .exclude(suite__name__in=job.notification.blacklist)
            )
            old_cases = (
                TestCase.objects.filter(
                    suite__job=args["query"]["results"][compare_index]
                )
                .exclude(name__in=job.notification.blacklist)
                .exclude(suite__name__in=job.notification.blacklist)
            )

            left_cases_diff = new_cases.exclude(
                name__in=old_cases.values_list("name", flat=True)
            )
            right_cases_diff = old_cases.exclude(
                name__in=new_cases.values_list("name", flat=True)
            )

            args["query"]["left_cases_diff"] = left_cases_diff
            args["query"]["right_cases_diff"] = right_cases_diff

            left_suites_intersection = new_suites.filter(
                name__in=old_suites.values_list("name", flat=True)
            )

            # Format results.
            left_suites_count = {}
            for suite in left_suites_intersection:
                left_suites_count[suite.name] = (
                    suite.testcase_set.filter(result=TestCase.RESULT_PASS).count(),
                    suite.testcase_set.filter(result=TestCase.RESULT_FAIL).count(),
                    suite.testcase_set.filter(result=TestCase.RESULT_SKIP).count(),
                )

            right_suites_intersection = old_suites.filter(
                name__in=new_suites.values_list("name", flat=True)
            )

            # Format results.
            right_suites_count = {}
            for suite in right_suites_intersection:
                right_suites_count[suite.name] = (
                    suite.testcase_set.filter(result=TestCase.RESULT_PASS).count(),
                    suite.testcase_set.filter(result=TestCase.RESULT_FAIL).count(),
                    suite.testcase_set.filter(result=TestCase.RESULT_SKIP).count(),
                )

            args["query"]["left_suites_count"] = left_suites_count
            args["query"]["right_suites_count"] = right_suites_count

            # Format {<Testcase>: old_result, ...}
            testcases_changed = {}
            for suite in left_suites_intersection:
                try:
                    old_suite = TestSuite.objects.get(
                        name=suite.name, job=args["query"]["results"][compare_index]
                    )
                except TestSuite.DoesNotExist:
                    continue  # No matching suite, move on.
                for testcase in suite.testcase_set.all():
                    try:
                        old_testcase = TestCase.objects.get(
                            suite=old_suite, name=testcase.name
                        )
                        if old_testcase and testcase.result != old_testcase.result:
                            testcases_changed[
                                testcase
                            ] = old_testcase.get_result_display()
                    except TestCase.DoesNotExist:
                        continue  # No matching TestCase, move on.
                    except TestCase.MultipleObjectsReturned:
                        logging.info(
                            "Multiple Test Cases with the equal name in TestSuite %s, could not compare",
                            old_suite,
                        )

            args["query"]["testcases_changed"] = testcases_changed

    return args


def create_irc_notification(job):
    args = {}
    args["job"] = job
    args["url_prefix"] = "http://%s" % dbutils.get_domain()
    return create_notification_body(Notification.DEFAULT_IRC_TEMPLATE, **args)


def create_notification_body(template_name, **kwargs):
    return Notification.TEMPLATES_ENV.get_template(template_name).render(**kwargs)


def get_recipient_args(recipient):
    user_data = {}
    if recipient.user:
        user_data["username"] = recipient.user.username
        user_data["first_name"] = recipient.user.first_name
        user_data["last_name"] = recipient.user.last_name
    return user_data


def send_notifications(job):
    logger = logging.getLogger("lava-scheduler")
    notification = job.notification
    # Prep template args.
    kwargs = get_notification_args(job)
    # Process notification callback.
    for callback in notification.notificationcallback_set.all():
        callback.invoke_callback()

    for recipient in notification.notificationrecipient_set.all():
        if recipient.method == NotificationRecipient.EMAIL:
            if recipient.status == NotificationRecipient.NOT_SENT:
                try:
                    logger.info(
                        "[%d] sending email notification to %s",
                        job.id,
                        recipient.email_address,
                    )
                    title = "LAVA notification for Test Job %s %s" % (
                        job.id,
                        job.description[:200],
                    )
                    kwargs["user"] = get_recipient_args(recipient)
                    body = create_notification_body(notification.template, **kwargs)
                    result = send_mail(
                        title, body, settings.SERVER_EMAIL, [recipient.email_address]
                    )
                    if result:
                        recipient.status = NotificationRecipient.SENT
                        recipient.save()
                except Exception as exc:
                    logger.exception(exc)
                    logger.warning(
                        "[%d] failed to send email notification to %s",
                        job.id,
                        recipient.email_address,
                    )
        else:  # IRC method
            if recipient.status == NotificationRecipient.NOT_SENT:
                if recipient.irc_server_name:
                    logger.info(
                        "[%d] sending IRC notification to %s on %s",
                        job.id,
                        recipient.irc_handle_name,
                        recipient.irc_server_name,
                    )
                    try:
                        irc_message = create_irc_notification(job)
                        utils.send_irc_notification(
                            Notification.DEFAULT_IRC_HANDLE,
                            recipient=recipient.irc_handle_name,
                            message=irc_message,
                            server=recipient.irc_server_name,
                        )
                        recipient.status = NotificationRecipient.SENT
                        recipient.save()
                        logger.info(
                            "[%d] IRC notification sent to %s",
                            job.id,
                            recipient.irc_handle_name,
                        )
                    # FIXME: this bare except should be constrained
                    except Exception as e:
                        logger.warning(
                            "[%d] IRC notification not sent. Reason: %s - %s",
                            job.id,
                            e.__class__.__name__,
                            str(e),
                        )


def notification_criteria(job_id, criteria, state, health, old_health):
    if "dependency_query" in criteria:
        # Makes sure that all the jobs from dependency list also satisfy the
        # criteria for sending notification.
        dependency_jobs = Query.get_queryset(
            ContentType.objects.get_for_model(TestJob),
            Query.parse_conditions(
                TestJob._meta.model_name, criteria["dependency_query"]
            ),
        ).exclude(pk=job_id)
        if criteria["status"] == "finished":
            if dependency_jobs.filter(~Q(state=TestJob.STATE_FINISHED)).count():
                return False

        if criteria["status"] == "running":
            if dependency_jobs.filter(~Q(state=TestJob.STATE_RUNNING)).count():
                return False

        if criteria["status"] == "complete":
            if dependency_jobs.filter(~Q(health=TestJob.HEALTH_COMPLETE)).count():
                return False
        elif criteria["status"] == "incomplete":
            if dependency_jobs.filter(~Q(health=TestJob.HEALTH_INCOMPLETE)).count():
                return False
        elif criteria["status"] == "canceled":
            if dependency_jobs.filter(~Q(health=TestJob.HEALTH_CANCELED)).count():
                return False

    # Support for "all"
    if criteria["status"] == "all":
        return state in [TestJob.STATE_RUNNING, TestJob.STATE_FINISHED]

    # support special status of finished, otherwise skip to normal
    if criteria["status"] == "finished":
        return state == TestJob.STATE_FINISHED

    if criteria["status"] == "running":
        return state == TestJob.STATE_RUNNING

    if criteria["status"] == "complete":
        const = TestJob.HEALTH_COMPLETE
    elif criteria["status"] == "incomplete":
        const = TestJob.HEALTH_INCOMPLETE
    else:
        const = TestJob.HEALTH_CANCELED

    # use normal notification support
    if health == const:
        if "type" in criteria:
            if criteria["type"] == "regression":
                if (
                    old_health == TestJob.HEALTH_COMPLETE
                    and health == TestJob.HEALTH_INCOMPLETE
                ):
                    return True
            if criteria["type"] == "progression":
                if (
                    old_health == TestJob.HEALTH_INCOMPLETE
                    and health == TestJob.HEALTH_COMPLETE
                ):
                    return True
        else:
            return True

    return False


def create_notification(job, data):
    # Create notification object.
    notification = Notification()

    if "verbosity" in data:
        notification.verbosity = Notification.VERBOSITY_MAP[data["verbosity"]]

    if "type" in data["criteria"]:
        notification.type = Notification.TYPE_MAP[data["criteria"]["type"]]

    if "compare" in data:
        if "blacklist" in data["compare"]:
            notification.blacklist = data["compare"]["blacklist"]
        if "query" in data["compare"]:
            query_data = data["compare"]["query"]
            if "username" in query_data:
                # DoesNotExist scenario already verified in validate
                username = query_data["username"]
                notification.query_owner = User.objects.get(username=username)
                notification.query_name = query_data["name"]
            else:  # Custom query.
                notification.entity = Query.get_content_type(query_data["entity"])
                if "conditions" in query_data:
                    # Save conditions as a string.
                    conditions = [
                        "%s%s%s" % (key, Query.CONDITION_DIVIDER, value)
                        for (key, value) in query_data["conditions"].items()
                    ]
                    notification.conditions = Query.CONDITIONS_SEPARATOR.join(
                        conditions
                    )

    notification.test_job = job
    notification.template = Notification.DEFAULT_TEMPLATE
    notification.save()

    if "recipients" in data:
        for recipient in data["recipients"]:
            notification_recipient = NotificationRecipient(notification=notification)
            notification_recipient.method = NotificationRecipient.METHOD_MAP[
                recipient["to"]["method"]
            ]
            if "user" in recipient["to"]:
                user = User.objects.get(username=recipient["to"]["user"])
                notification_recipient.user = user
            if "email" in recipient["to"]:
                notification_recipient.email = recipient["to"]["email"]
            if "handle" in recipient["to"]:
                notification_recipient.irc_handle = recipient["to"]["handle"]
            if "server" in recipient["to"]:
                notification_recipient.irc_server = recipient["to"]["server"]

            # Ignore unique constraint violation.
            with contextlib.suppress(IntegrityError):
                notification_recipient.save()

    else:
        # You can do "callbacks only" without having recipients, in that
        # case, no notification will be sent.
        if "callbacks" not in data and "callback" not in data:
            # But if there's no callback and no recipients then we add a
            # submitter as a default recipient.
            # Ignore unique constraint violation.
            with contextlib.suppress(IntegrityError):
                notification_recipient = NotificationRecipient.objects.create(
                    user=job.submitter, notification=notification
                )

    # Add callbacks.
    if "callbacks" in data:
        for callback in data["callbacks"]:
            create_callback(job, callback, notification)
    if "callback" in data:
        create_callback(job, data["callback"], notification)
