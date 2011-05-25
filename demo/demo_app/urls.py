from django.conf.urls.defaults import url, patterns


urlpatterns = patterns(
    'demo_app.views',
    url(r'hello$', 'hello'))
