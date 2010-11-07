from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url(r'^static/(?P<path>.*)$', 'staticfiles.views.serve'),
)
