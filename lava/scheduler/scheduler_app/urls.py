from django.conf.urls.defaults import *
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from lava.scheduler.scheduler_app.views import (
    index,
    submit,
)

#urlpatterns = patterns('scheduler_app.views',
urlpatterns = patterns(
    '',
    url(r'^$',
        index,
        name='scheduler_app.index'),
    url(r'^submit/',
        submit,
        name='scheduler_app.submit'),
        
    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    #(r'^admin/', include(admin.site.urls)),
    url(r'^admin/',
        include(admin.site.urls)),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        (r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    )
