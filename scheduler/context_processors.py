from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.http import urlquote

def handy_urls(request):
    print 'hi'
    path = urlquote(request.get_full_path())
    login_url = '%s?%s=%s' % (settings.LOGIN_URL, REDIRECT_FIELD_NAME, path)
    logout_url = '%s' % (settings.LOGOUT_URL)
    return {
        'login_url': login_url,
        'logout_url': logout_url,
        }
