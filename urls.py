# -*- coding: utf-8 -*-

from django.conf.urls.defaults import *
from django.contrib import admin
from django_authopenid import views as oid_views
from tastypie.api import Api

from feeds import LatestSnippets, LatestTag, LatestUser

from snippets import views as snippets_views
from snippets import resources as snippets_resources

from accounts.forms import OpenidRegisterForm
from accounts import views as auth_views

admin.autodiscover()

feeds = {
    'latest': LatestSnippets,
    'tag': LatestTag,
    'user': LatestUser
}
v1_api = Api(api_name='v1')
v1_api.register(snippets_resources.SnippetResource())

urlpatterns = patterns('',
    #First page
    url(r'^/?$', snippets_views.snippets_index, name="snippets_index"),

    #Snippets urls
    url(r'^snippets/?$', snippets_views.index, name="snippets_my_index"),
    url(r'^(\d+)-?.*/?$', snippets_views.read, name="snippets_read"),
    url(r'^create/?$', snippets_views.process, name="snippets_create"),
    url(r'^update/(\d+)/?$', snippets_views.process, name="snippets_update"),
    url(r'^preview/?$', snippets_views.preview, name="snippets_preview"),
    url(r'^delete/(\d+)/?$', snippets_views.delete, name="snippets_delete"),
    url(r'^download/(\d+)/?$', snippets_views.download,
                                            name="snippets_download"),
    url(r'^history/(\d+)/?$', snippets_views.history, name="snippets_history"),
    url(r'^comment/(\d+)/?$', snippets_views.comment, name="snippets_comment"),
    url(r'^search/?$', snippets_views.search, name="snippets_search"),
    url(r'^suggest/?$', snippets_views.suggest, name="snippets_suggest"),

    #Tags
    url(r'^tag/(?P<tag>[^/]+)/?$', snippets_views.tag_view, name="tag_view"),
    url(r'^tag/(?P<tag>[^/]+)/(?P<username>[^/]+)/?$', snippets_views.tag_user,
        name="tag_user"),
    url(r'^tags/?$', snippets_views.tags_index, name="tags_index"),

    #REST
    url(r'^api/', include(v1_api.urls)),

    #Accounts
    url(r'^account/register/$', oid_views.register, {
        'register_form': OpenidRegisterForm,
        'register_account': auth_views.register_account
        },  name='user_register'),
    url(r'^account/', include('django_authopenid.urls')),
    url(r'^accounts/', include('accounts.urls')),

    #Others
    url(r'^search-plugin.xml$',
        'django.views.generic.simple.direct_to_template', {
            'template': 'snippets/search-plugin.xml',
            'extra_context': {'SITE': ''}
        }, name="search_plugin"),

    url(r'^feeds/(?P<url>.*)/?$', 'django.contrib.syndication.views.feed',
        {'feed_dict': feeds}, name="feeds"),

    url(r'^admin/', include(admin.site.urls)),
)
