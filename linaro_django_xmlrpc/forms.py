# Copyright (C) 2010, 2011 Linaro Limited
#
# Author: Zygmunt Krynicki <zygmunt.krynicki@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

"""
Forms
"""

from django import forms

from linaro_django_xmlrpc.models import AuthToken


class AuthTokenForm(forms.ModelForm):
    class Meta:
        model = AuthToken
        fields = ("description",)
