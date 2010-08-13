from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib import admin
from django.views.generic.simple import direct_to_template

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', direct_to_template,
        name='home',
        kwargs={'template': 'index.html'}),
    url(r'^about-alpha/', direct_to_template,
        name='about-alpha',
        kwargs={'template': 'about_alpha.html'}),
    (r'^admin/', include(admin.site.urls)),
    )

if settings.STANDALONE:
    # This is only used for standalone installations It is _not_ secure
    # (see django docs) and should _never_ be used in production
    # environments.
    urlpatterns += patterns('',
            (r'^site_media/(?P<path>.*)$', 'django.views.static.serve', {
                'document_root': settings.MEDIA_ROOT,
                'show_indexes': True}))

