import os
import yaml
import logging
from django.utils.translation import ungettext_lazy
from django.conf import settings


def help_max_length(max_length):
    return ungettext_lazy(
        u"Maximum length: {0} character",
        u"Maximum length: {0} characters",
        max_length).format(max_length)


class StreamEcho(object):
    def write(self, value):
        return value


def description_filename(job_id):
    logger = logging.getLogger('lava_results_app')
    filename = os.path.join(settings.MEDIA_ROOT, 'job-output', 'job-%s' % job_id, 'description.yaml')
    if not os.path.exists(filename):
        logger.error("No description.yaml for job %s" % job_id)
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
