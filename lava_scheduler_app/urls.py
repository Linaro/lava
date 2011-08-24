from django.conf.urls.defaults import url, patterns

urlpatterns = patterns(
    'lava_scheduler_app.views',
    url(r'^$', 'index'),
    url(r'^alljobs$', 'alljobs'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)$', 'device'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/maintenance$', 'device_maintenance_mode'),
    url(r'^device/(?P<pk>[-_a-zA-Z0-9]+)/online$', 'device_online'),
    url(r'^job/(?P<pk>[0-9]+)$', 'job'),
    url(r'^job/(?P<pk>[0-9]+)/cancel$', 'job_cancel'),
    url(r'^job/(?P<pk>[0-9]+)/json$', 'job_json'),
    url(r'^job/(?P<pk>[0-9]+)/output$', 'job_output'),
    )
