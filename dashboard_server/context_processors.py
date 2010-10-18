from django.conf import settings

def login_url(request):
    return dict(login_url=settings.LOGIN_URL)
