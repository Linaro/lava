# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# This file is part of linaro-django-xmlrpc.
#
# linaro-django-xmlrpc is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License version 3
# as published by the Free Software Foundation
#
# linaro-django-xmlrpc is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with linaro-django-xmlrpc.  If not, see <http://www.gnu.org/licenses/>.

"""
XML-RPC views
"""

import base64

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.sites.models import Site
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from lava_server.bread_crumbs import BreadCrumb, BreadCrumbTrail
from lava_server.views import index as lava_index
from linaro_django_xmlrpc.forms import AuthTokenForm
from linaro_django_xmlrpc.models import AuthToken, CallContext, Dispatcher, SystemAPI


@csrf_exempt
def handler(request, mapper, help_view):
    """
    XML-RPC handler.

    If post data is defined, it assumes it's XML-RPC and tries to process as
    such. Empty POST request and GET requests assumes you're viewing from a
    browser and tells you about the service by redirecting you to a dedicated
    help page. For backwards compatibility the help view defaults to the
    'default_help' that shows what is registered in the global mapper. If you
    want to show help specific to your mapper you must specify help_view. It
    accepts whatever django.shortcuts.redirect() would.
    """
    if len(request.body) == 0 or request.method != "POST":
        return redirect(help_view)

    raw_data = request.body
    dispatcher = Dispatcher(mapper)

    auth_string = request.META.get("HTTP_AUTHORIZATION")

    if auth_string is not None:
        if " " not in auth_string:
            return HttpResponse("Invalid HTTP_AUTHORIZATION header", status=400)
        scheme, value = auth_string.split(" ", 1)
        if scheme != "Basic":
            return HttpResponse(
                "Unsupported HTTP_AUTHORIZATION header, only Basic scheme is supported",
                status=400,
            )
        try:
            decoded_value = base64.standard_b64decode(value).decode("utf-8")
        except (TypeError, UnicodeDecodeError):
            return HttpResponse(
                "Corrupted HTTP_AUTHORIZATION header, bad base64 encoding",
                status=400,
            )
        try:
            username, secret = decoded_value.split(":", 1)
        except ValueError:
            return HttpResponse(
                "Corrupted HTTP_AUTHORIZATION header, no user:pass", status=400
            )
        user = AuthToken.get_user_for_secret(username, secret)
        if user is None:
            response = HttpResponse("Invalid token", status=401)
            response["WWW-Authenticate"] = 'Basic realm="XML-RPC Authentication token"'
            return response
    else:
        user = request.user

    result = dispatcher.marshalled_dispatch(raw_data, user, request)
    response = HttpResponse(content_type="application/xml")
    response.write(result)
    response["Content-length"] = str(len(response.content))
    return response


@BreadCrumb("API help", parent=lava_index)
def help(request, mapper, template_name="linaro_django_xmlrpc/api.html"):
    context = CallContext(user=None, mapper=mapper, dispatcher=None)
    system = SystemAPI(context)
    if settings.HTTPS_XML_RPC:
        scheme = "https"
    else:
        scheme = request.META.get("REQUEST_SCHEME", "http")
    scheduler_methods = []
    results_methods = []
    system_methods = []
    for method in system.listMethods():
        if "scheduler" in method:
            scheduler_methods.append(method)
        elif "results" in method:
            results_methods.append(method)
        else:
            system_methods.append(method)
    methods = {
        "scheduler": [
            {
                "name": method,
                "section": method.rsplit(".", 1)[0] if "." in method else "",
                "signature": system.methodSignature(method),
                "help": system.methodHelp(method),
            }
            for method in scheduler_methods
        ],
        "results": [
            {
                "name": method,
                "signature": system.methodSignature(method),
                "help": system.methodHelp(method),
            }
            for method in results_methods
        ],
        "system": [
            {
                "name": method,
                "signature": system.methodSignature(method),
                "help": system.methodHelp(method),
            }
            for method in system_methods
        ],
    }
    domain = Site.objects.get_current().domain
    return render(
        request,
        template_name,
        {
            "methods": methods,
            "context_help": ["data-export"],
            "bread_crumb_trail": BreadCrumbTrail.leading_to(help),
            "site_scheme": scheme,
            "site_domain": domain,
            "site_url": "{scheme}://{domain}".format(scheme=scheme, domain=domain),
        },
    )


@BreadCrumb("API tokens", parent=lava_index)
@login_required
def tokens(request):
    """
    List of tokens for an authenticated user
    """
    token_list = AuthToken.objects.filter(user=request.user).order_by("last_used_on")
    unused = AuthToken.objects.filter(
        user=request.user, last_used_on__isnull=True
    ).count()
    return render(
        request,
        "linaro_django_xmlrpc/tokens.html",
        {
            "token_list": token_list,
            "unused": unused,
            "bread_crumb_trail": BreadCrumbTrail.leading_to(tokens),
            "context_help": ["first_steps"],
        },
    )


@login_required
def create_token(request):
    """
    Create a token for the requesting user
    """
    if request.method == "POST":
        form = AuthTokenForm(request.POST)
        if form.is_valid():
            form.save(commit=False)
            form.instance.user = request.user
            form.instance.save()
            return HttpResponseRedirect(reverse("linaro_django_xmlrpc_tokens"))
    else:
        form = AuthTokenForm()
    return render(request, "linaro_django_xmlrpc/create_token.html", {"form": form})


@login_required
def delete_token(request, object_id):
    token = get_object_or_404(AuthToken, pk=object_id, user=request.user)
    if request.method == "POST":
        token.delete()
        return HttpResponseRedirect(reverse("linaro_django_xmlrpc_tokens"))
    return render(
        request, "linaro_django_xmlrpc/authtoken_confirm_delete.html", {"token": token}
    )


@login_required
def edit_token(request, object_id):
    token = get_object_or_404(AuthToken, pk=object_id, user=request.user)
    if request.method == "POST":
        form = AuthTokenForm(request.POST, instance=token)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse("linaro_django_xmlrpc_tokens"))
    else:
        form = AuthTokenForm(instance=token)
    return render(
        request, "linaro_django_xmlrpc/edit_token.html", {"token": token, "form": form}
    )


@login_required
def delete_unused_tokens(request):
    token_list = AuthToken.objects.filter(user=request.user, last_used_on__isnull=True)
    if request.method == "POST":
        for token in token_list:
            token.delete()
        return HttpResponseRedirect(reverse("linaro_django_xmlrpc_tokens"))
    return render(
        request,
        "linaro_django_xmlrpc/tokens.html",
        {"token_list": token_list, "context_help": ["lava-tool"]},
    )
