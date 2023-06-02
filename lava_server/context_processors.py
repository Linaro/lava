# Copyright (C) 2010-2018 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.conf import settings

from lava_common.version import __version__


def lava(request):
    return {
        "lava": {
            "instance_name": settings.INSTANCE_NAME,
            "instance_version": __version__,
            "branding_url": settings.BRANDING_URL,
            "branding_icon": settings.BRANDING_ICON,
            "branding_alt": settings.BRANDING_ALT,
            "branding_height": settings.BRANDING_HEIGHT,
            "branding_width": settings.BRANDING_WIDTH,
            "branding_bug_url": settings.BRANDING_BUG_URL,
            "branding_source_url": settings.BRANDING_SOURCE_URL,
            "branding_message": settings.BRANDING_MESSAGE,
            "branding_css": settings.BRANDING_CSS,
        }
    }


def ldap_available(request):
    ldap_enabled = (
        "django_auth_ldap.backend.LDAPBackend" in settings.AUTHENTICATION_BACKENDS
    )
    login_message_ldap = getattr(settings, "LOGIN_MESSAGE_LDAP", "")
    return {"ldap_available": ldap_enabled, "login_message_ldap": login_message_ldap}


def oidc_context(request):
    return {
        "oidc_enabled": settings.OIDC_ENABLED,
        "oidc_account_name": settings.LAVA_OIDC_ACCOUNT_NAME,
    }


def socialaccount(request):
    return {
        "socialaccount_enabled": settings.AUTH_SOCIALACCOUNT
        or settings.AUTH_GITLAB_URL,
    }
