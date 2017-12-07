import os
import yaml
import logging
import subprocess
from django.utils.translation import ungettext_lazy
from django.conf import settings
from django.core.exceptions import PermissionDenied
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


class V2Loader(yaml.Loader):
    def remove_pipeline_module(self, suffix, node):
        if 'lava_dispatcher.pipeline' in suffix:
            suffix = suffix.replace('lava_dispatcher.pipeline', 'lava_dispatcher')
        return self.construct_python_object(suffix, node)

    def remove_pipeline_module_name(self, suffix, node):
        if 'lava_dispatcher.pipeline' in suffix:
            suffix = suffix.replace('lava_dispatcher.pipeline', 'lava_dispatcher')
        return self.construct_python_name(suffix, node)

    def remove_pipeline_module_new(self, suffix, node):
        if 'lava_dispatcher.pipeline' in suffix:
            suffix = suffix.replace('lava_dispatcher.pipeline', 'lava_dispatcher')
        return self.construct_python_object_new(suffix, node)


V2Loader.add_multi_constructor(
    u'tag:yaml.org,2002:python/name:',
    V2Loader.remove_pipeline_module_name)
V2Loader.add_multi_constructor(
    u'tag:yaml.org,2002:python/object:',
    V2Loader.remove_pipeline_module)
V2Loader.add_multi_constructor(
    u'tag:yaml.org,2002:python/object/new:',
    V2Loader.remove_pipeline_module_new)


def description_data(job):
    logger = logging.getLogger('lava_results_app')
    filename = description_filename(job)
    if not filename:
        return {}
    try:
        data = yaml.load(open(filename, 'r'), Loader=V2Loader)
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
        raise PermissionDenied()
    if not auth_user:
        raise PermissionDenied()
    return auth_user


def check_request_auth(request, job):
    if job.is_public:
        return
    if not request.user.is_authenticated():
        # handle anonymous access
        auth_user = anonymous_token(request, job)
        if not auth_user or not job.can_view(auth_user):
            raise PermissionDenied()
    elif not job.can_view(request.user):
        raise PermissionDenied()


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
        # example version returned would be '2016.11-1'
        return deb_version
