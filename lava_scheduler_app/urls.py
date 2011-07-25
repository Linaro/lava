from django.conf.urls.defaults import url, patterns

urlpatterns = patterns(
    'lava_scheduler_app.views',
    url(r'^$', 'index'),
    url(r'^alljobs$', 'alljobs'),
    url(r'^job/(?P<pk>[0-9]+)$', 'job'),
    url(r'^job/(?P<pk>[0-9]+)/output$', 'job_output'),
    )
