# -*- coding: utf-8 -*-
""" Snippets views """

import difflib
import json

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import guess_lexer, get_lexer_by_name, LEXERS
from pygments.util import ClassNotFound
from pygments.styles import get_all_styles

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, render_to_response
from django.template.loader import render_to_string

from django_emailqueue.models import EmailQueue
from taggit.models import Tag

from snippify.accounts.models import UserProfile
from snippify.utils import build_context, JsonResponse

from forms import SnippetForm
from models import Snippet, SnippetVersion, SnippetComment

def snippets_index(request):
    """ Used for the front page. Return latest 5 snippets"""

    snippets = Snippet.objects.all()[:5]
    if snippets == None:
        snippets = []
    return render_to_response('pages/index.html', {
        'snippets': snippets, 'home_page': True },
                            context_instance=build_context(request))

def read(request, id=None):
    """Show a snippet with title, tags and render pygments body"""

    snippet = get_object_or_404(Snippet, pk=id)
    if len(SnippetVersion.objects.filter(snippet=snippet).all()):
        versions = True
    else:
        versions = False

    comments_paginator = Paginator(SnippetComment.objects.filter(
                                                    snippet=snippet).all(), 2)
    try:
        comments = comments_paginator.page(int(request.GET.get('page', 1)))
    except EmptyPage:
        comments  = None

    snippet.highlight_body = snippet.highlight(snippet.body,
                                            get_lexer_by_name(snippet.lexer))

    return render_to_response('snippets/read.html', {
                'snippet': snippet,
                'comments': comments,
                'versions': versions,
                'styles': get_all_styles(),
                'lines': range(1, snippet.body.count('\n')+2),
            }, context_instance=build_context(request))

def history(request, id = None):
    """ Show history list or display diff between two versions """

    snippet = get_object_or_404(Snippet, pk=id)
    if request.GET.get('v'):
        version = int(request.GET['v'])
        if version == 0:
            body = snippet.highlight(snippet.body,
                                     get_lexer_by_name(snippet.lexer))
        else:
            ver = get_object_or_404(SnippetVersion, snippet=snippet,
                                    version=version)
            body = snippet.highlight(ver.body,
                                     get_lexer_by_name(snippet.lexer))
        return render_to_response('snippets/version.html', {
                'snippet': snippet,
                'version': version,
                'body': body,
                'lines': range(1, body.count('\n'))
            }, context_instance=build_context(request))

    elif request.GET.get('v1') and request.GET.get('v2'):
        version1 = int(request.GET['v1'])
        version2 = int(request.GET['v2'])
        if version1 == 0:
            version1_label = 'current'
            body_1 = snippet.body
        else:
            version1_label = 'v' + str(version1)
            body_1 = get_object_or_404(SnippetVersion, snippet=snippet,
                                       version=version1).body
        if version2 == 0:
            version2_label = 'current'
            body_2 = snippet.body
        else:
            version2_label = 'v' + str(version2)
            body_2 = get_object_or_404(SnippetVersion, snippet=snippet,
                                       version=version2).body
        fromlines = str(body_1).splitlines(True)
        tolines = str(body_2).splitlines(True)

        if len(fromlines) >= len(tolines):
            no = len(fromlines) #XXX: this is unused
        else:
            no = len(tolines)
        diffbody = ''
        for line in difflib.unified_diff(fromlines, tolines,
                                         fromfile=version1_label,
                                         tofile=version2_label):
            diffbody = diffbody + str(line)
        diffbody = snippet.highlight(diffbody, get_lexer_by_name('diff'))
        return render_to_response('snippets/diff.html', {
            'snippet': snippet,
            'version1': version1,
            'version2': version2,
            'diffbody': diffbody,
            'lines': range(1, diffbody.count('\n'))
        },
        context_instance=build_context(request))
    else:
        snippet_versions = SnippetVersion.objects.filter(snippet=snippet).all()
        return render_to_response('snippets/history_index.html', {
            'snippet': snippet,
            'snippet_versions': snippet_versions
            }, context_instance=build_context(request))

@login_required
def index(request):
    """My snippets"""

    snippets = Snippet.objects.filter(author=request.user)
    return render_to_response('snippets/index.html', {'snippets': snippets},
                            context_instance=build_context(request))

@login_required
def process(request, id=None):
    """ Create/Update snippet """

    if id is not None:#Update
        snippet = get_object_or_404(Snippet, pk=id)
        form = SnippetForm(instance=snippet)
        if not request.user.is_staff or request.user != snippet.author:
            request.session['flash'] = ['Access denied', 'error']
            return HttpResponseRedirect('/accounts/profile/')

        if 'delete' in request.POST:
            snippet.delete()
            request.session['flash'] = ['#%s deleted successfuly' % id,
                                        'sucess']
            return HttpResponseRedirect('/accounts/profile/')

    else: #Create
        snippet = None
        form = SnippetForm()

    if request.method == 'POST':
        form = SnippetForm(request.POST)#Bounding form to the POST data
        if not form.is_valid(): # redirect to form with errors
            return render_to_response('snippets/process.html', {
                'form': form
                }, context_instance=build_context(request))

        formData = form.save(commit = False)
        formData.pk = id
        if 'preview' in request.POST:
            data = {}
            data['title'] = formData.title
            data['preview_body'] = highlight(formData.body,
                                            get_lexer_by_name(formData.lexer),
                                            HtmlFormatter(cssclass = 'source'))
            data['lines'] = range(1, formData.body.count('\n') + 2)
            data['form'] = form
            data['snippet'] = formData
            return render_to_response('snippets/process.html', data,
                                      context_instance=build_context(request))
        else:#save
            formData.author = request.user
            if not formData.lexer:
                try:
                    lexer = guess_lexer(formData.body)
                    for lex in LEXERS.itervalues():
                        if lexer.name == lex[1]:
                            formData.lexer = lex[2][0].lower()
                except ClassNotFound:
                    formData.lexer = 'text'
            formData.save()
            if snippet is not None and snippet.body != formData.body:
                try:
                    last_version =SnippetVersion.objects.order_by('-version').\
                                            filter(snippet = snippet).all()[0]
                    new_version = SnippetVersion(snippet = snippet,
                                                 version =
                                                 last_version.version + 1,
                                                 body = snippet.body)
                    new_version.save()
                except:
                    create_version = SnippetVersion(snippet = snippet,
                                                    version = 1,
                                                    body = snippet.body)
                    create_version.save()
            request.session['flash'] = ['#%s %s successfuly' % (formData.pk,
                'update' if id is not None else 'created'), 'sucess']
            return HttpResponseRedirect('/accounts/profile/')
    else:
        return render_to_response('snippets/process.html', {
            'form': form,
            'snippet': snippet
        }, context_instance=build_context(request))

@login_required
def delete(request, id=None):
    """Delete a snippet, only the author and staff can delete"""

    snippet = get_object_or_404(Snippet, pk=id)
    if snippet.author_id == request.user.id or request.user.is_staff:
        snippet.delete()
        request.session['flash'] = ['#%s deleted succesfully' % id, 'success']
        return HttpResponseRedirect(request.META.get('HTTP_REFERER',
                                                     '/accounts/profile'))
    else:
        request.session['flash'] = ['Access denied', 'error']
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

def comment(request, id = None):
    """ Create a new comment. Django comments framework sucks! """

    if request.GET.get('delete'):
        if request.user.is_staff:
            get_object_or_404(SnippetComment, pk=id).delete()
            request.session['flash'] = ['Comment deleted succesfully',
                                        'success']
        else:
            request.session['flash'] = ['Permission denied', 'error']
        return HttpResponseRedirect(request.META.get('HTTP_REFERER',
                                                     '/accounts/profile/'))
    else:
        data = {}
        snippet = get_object_or_404(Snippet, pk=id)
        if request.user.is_authenticated:
            body = request.POST.get('body')
            if body:
                comment = SnippetComment(snippet=snippet, user=request.user,
                                         body=body)
                comment.save()
                 # send notification if you are not the author
                if snippet.author != request.user:
                    profile = UserProfile.objects.get(user=snippet.author)
                    #User wants to recieve a notification
                    if profile.user_commented:
                        queue = EmailQueue(
                            mail_to=snippet.author.email,
                            mail_subject="Your snippet has been commented",
                            mail_body=render_to_string(
                                'emails/user_commented.txt', {
                                    'user': snippet.author,
                                    'username': request.user.username,
                                    'comment': comment,
                                    'snippet': snippet,
                                    'SITE': request.META['HTTP_HOST']
                                }
                            )
                        )
                        queue.save()
                data['content'] = render_to_string('elements/comment.html',
                                                   {'comment': comment})
            else:
                data['error'] = 'Body field is required'
        else:
            data['error'] = 'You must login to post a comment'
        return JsonResponse(data)

def search(request):
    """ Search using haystack """

    data = {}
    data['query'] = request.GET.get('q', '')
    paginator = Paginator(Snippet.indexer.search(data['query']).prefetch(), 25)
    data['results'] = paginator.page(int(request.GET.get('page', 1)))
    return render_to_response('snippets/search.html', data,
                              context_instance=build_context(request))

def suggest(request):
    """ This is used for search-plugin.xml (used to suggest search results in
    FF and maybe other browsers

    """

    data = []
    query = request.GET.get('q', '')
    results = Snippet.indexer.search(query).prefetch()
    data.append(query)
    results_list = []
    for result in results:
        results_list.append(result.instance.title)
    data.append(results_list)
    return HttpResponse(json.dumps(data))

def download(request, id=None):
    """ Download snippet as text file """

    snippet = get_object_or_404(Snippet, pk=id)
    try:
        file_extention = get_lexer_by_name(snippet.lexer).\
                                            filenames[0].split('*')[1]
        file_mimetype = get_lexer_by_name(snippet.lexer).mimetypes[0]
    except:
        file_extention = '.txt'
        file_mimetype = 'text/plain'

    filename = str(snippet.title).lower().replace(' ','_') + file_extention
    response = HttpResponse(snippet.body, content_type=file_mimetype)
    response['Content-Length'] = len(snippet.body)
    response['Content-Disposition'] = 'attachment; filename="' + filename + '"'
    return response

# Tags views
def tags_index(request):
    """ View for all tags """

    tags = Tag.objects.all()
    return render_to_response('tags/index.html', {},
                              context_instance=build_context(request))

def tag_view(request, tag = None):
    """ Show snippets of some tag """
    try:
        tag_object = Tag.objects.get(name=tag)
        snippets = TaggedItem.objects.get_by_model(Snippet, tag_object)
    except:
        snippets = None
    return render_to_response('tags/view.html', {
        'tag': tag,
        'snippets': snippets
        }, context_instance=build_context(request))

def tag_user(request, tag = None, username = None):
    """ Display all `tag` snippets of `username` user """

    try:
        tag_object = Tag.objects.get(name=tag)
        snippets = TaggedItem.objects.get_by_model(Snippet, tag_object)
    except:
        snippets = None
    return render_to_response('tags/view.html', {
        'tag': tag,
        'snippets': snippets
        }, context_instance=build_context(request))
