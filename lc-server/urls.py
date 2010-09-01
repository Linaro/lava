from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template

from launch_control.dashboard_app.views import dashboard_xml_rpc_handler


admin.autodiscover()


urlpatterns = patterns('',
    url(r'^$', direct_to_template,
        name='home',
        kwargs={'template': 'index.html'}),
    url(r'^about-alpha/', direct_to_template,
        name='about-alpha',
        kwargs={'template': 'about_alpha.html'}),
    url(r'^xml-rpc/', dashboard_xml_rpc_handler,
        name='xml-rpc-handler'),
    (r'^admin/', include(admin.site.urls)),
    )

if not settings.CONFIGURED:
    # This is only used when we cannot count on static media files being
    # served by some real web server. WARNING: this is not secure and
    # should _never_ be used in production environments.
    # See:
    # http://docs.djangoproject.com/en/1.2/howto/static-files/#the-big-fat-disclaimer)
    urlpatterns += patterns('',
            (r'^site_media/(?P<path>.*)$', 'django.views.static.serve', {
                'document_root': settings.MEDIA_ROOT,
                'show_indexes': True}))

