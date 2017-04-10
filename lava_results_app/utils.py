import os
import yaml
import logging
import subprocess
from django.utils.translation import ungettext_lazy
from django.conf import settings
from django.http import Http404
from linaro_django_xmlrpc.models import AuthToken


def help_max_length(max_length):
    return ungettext_lazy(  # pylint: disable=no-member
        u"Maximum length: {0} character",
        u"Maximum length: {0} characters",
        max_length).format(max_length)


class StreamEcho(object):  # pylint: disable=too-few-public-methods
    def write(self, value):  # pylint: disable=no-self-use,
        return value


def description_filename(job):
    filename = os.path.join(job.output_dir, 'description.yaml')
    if not os.path.exists(filename):
        return None
    return filename


def description_data(job):
    logger = logging.getLogger('lava_results_app')
    filename = description_filename(job)
    if not filename:
        return {}
    try:
        data = yaml.load(open(filename, 'r'))
    except yaml.YAMLError:
        logger.error("Unable to parse description for %s" % job.id)
        return {}
    if not data:
        return {}
    return data


# FIXME: relocate these two functions into dbutils to avoid needing django settings here.
# other functions in utils can be run outside django. Remove import of AuthToken.
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


def debian_package_version():
    """
    Relies on Debian Policy rules for the existence of the
    changelog. Distributions not derived from Debian will
    return an empty string.
    """
    changelog = '/usr/share/doc/lava-server/changelog.Debian.gz'
    if os.path.exists(changelog):
        deb_version = subprocess.check_output((
            'dpkg-query', '-W', "-f=${Version}\n", 'lava-server')).strip().decode('utf-8')
        # example version returned would be '2016.11'
        return deb_version.split('-')[0]
