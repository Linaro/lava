from django.conf.urls import *


urlpatterns = patterns(
    'lava_markitup.views',
    url('^markdown/$', 'preview_markdown', name='lava.markitup.markdown'),
)
