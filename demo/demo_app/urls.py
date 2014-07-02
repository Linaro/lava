from django.conf.urls import url, patterns


urlpatterns = patterns(
    'demo_app.views',
    url(r'hello$', 'hello'))
