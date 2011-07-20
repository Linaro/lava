from django.conf.urls.defaults import url, patterns

urlpatterns = patterns(
    'lava_scheduler_app.views',
    url(r'^$', 'index'),
    url(r'^alljobs$', 'alljobs'),
    )
