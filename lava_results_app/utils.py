import os
import yaml
import logging
from django.utils.translation import ungettext_lazy
from django.conf import settings
from django.http import Http404
from linaro_django_xmlrpc.models import AuthToken


def help_max_length(max_length):
    return ungettext_lazy(
        u"Maximum length: {0} character",
        u"Maximum length: {0} characters",
        max_length).format(max_length)


class StreamEcho(object):
    def write(self, value):
        return value


def description_filename(job_id):
    filename = os.path.join(settings.MEDIA_ROOT, 'job-output', 'job-%s' % job_id, 'description.yaml')
    if not os.path.exists(filename):
        return None
    return filename


def description_data(job_id):
    logger = logging.getLogger('lava_results_app')
    filename = description_filename(job_id)
    if not filename:
        return {}
    try:
        data = yaml.load(open(filename, 'r'))
    except yaml.YAMLError:
        logger.error("Unable to parse description for %s" % job_id)
        return {}
    if not data:
        return {}
    return data


def anonymous_token(request, job):
    querydict = request.GET
    user = querydict.get('user', default=None)
    token = querydict.get('token', default=None)
    # safe to call with (None, None) - returns None
    auth_user = AuthToken.get_user_for_secret(username=user, secret=token)
    if not user and not job.is_public:
        raise Http404("Job %d requires authentication to view." % job.id)
    if not auth_user:
        raise Http404("User '%s' is not able to view job %d" % (user, job.id))
    return auth_user


def check_request_auth(request, job):
    if job.is_public:
        return
    if not request.user.is_authenticated():
        # handle anonymous access
        auth_user = anonymous_token(request, job)
        if not auth_user or not job.can_view(auth_user):
            raise Http404("User '%s' is not able to view job %d" % (request.user, job.id))
    elif not job.can_view(request.user):
        raise Http404("User '%s' is not able to view job %d" % (request.user.username, job.id))
