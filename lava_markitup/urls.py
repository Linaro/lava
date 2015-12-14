from django.conf.urls import url
from lava_markitup.views import preview_markdown


urlpatterns = [
    url('^markdown/$', preview_markdown, name='lava.markitup.markdown'),
]
