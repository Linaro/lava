.. index:: user authentication

.. _user_authentication:

Configuring user authentication
===============================

The LAVA frontend is developed using the Django_ web application framework and
user authentication and authorization is based on the standard `Django auth
subsystems`_. This means that it is fairly easy to integrate authentication
against any source for which a Django backend exists. Discussed below are the
tested and supported authentication methods for LAVA.

.. _Django: https://www.djangoproject.com/
.. _`Django auth subsystems`: https://docs.djangoproject.com/en/3.2/topics/auth/

.. note:: LAVA used to include support for OpenID authentication (prior to
   version 2016.8), but this support had to be **removed** when incompatible
   changes in Django (version 1.8) caused it to break.

Local Django user accounts are supported. When using local Django user
accounts, new user accounts need to be created by Django admin prior to use.

.. seealso:: :ref:`admin_adding_users`

.. _ldap_authentication:

Using Lightweight Directory Access Protocol (LDAP)
--------------------------------------------------

LAVA server may be configured to authenticate via Lightweight
Directory Access Protocol (LDAP). LAVA uses the `django_auth_ldap`_
backend for LDAP authentication.

.. _`django_auth_ldap`: https://django-auth-ldap.readthedocs.io/en/latest/

LDAP server support is configured using the following parameters in
``/etc/lava-server/settings.conf`` (JSON syntax)::

  "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
  "AUTH_LDAP_BIND_DN": "",
  "AUTH_LDAP_BIND_PASSWORD": "",
  "AUTH_LDAP_USER_DN_TEMPLATE": "uid=%(user)s,ou=users,dc=example,dc=com",
  "AUTH_LDAP_USER_ATTR_MAP": {
    "first_name": "givenName",
    "email": "mail"
  },

Use the following parameter to configure a custom LDAP login page
message::

    "LOGIN_MESSAGE_LDAP": "If your Linaro email is first.second@linaro.org then use first.second as your username"

Other supported parameters are::

  "AUTH_LDAP_GROUP_SEARCH": "LDAPSearch('ou=groups,dc=example,dc=com', ldap.SCOPE_SUBTREE, '(objectClass=groupOfNames)'",
  "AUTH_LDAP_USER_FLAGS_BY_GROUP": {
    "is_active": "cn=active,ou=django,ou=groups,dc=example,dc=com",
    "is_staff": "cn=staff,ou=django,ou=groups,dc=example,dc=com",
    "is_superuser": "cn=superuser,ou=django,ou=groups,dc=example,dc=com"
  }

Similarly::

  "AUTH_LDAP_USER_SEARCH": "LDAPSearch('o=base', ldap.SCOPE_SUBTREE, '(uid=%(user)s)')"

.. note:: If you need to make deeper changes that don't fit into the
          exposed configuration, it is quite simple to tweak things in
          the code here. Edit
          ``/usr/lib/python3/dist-packages/lava_server/settings/common.py``

Restart the ``lava-server`` and ``apache2`` services after any
changes.

Using external authentication provider supported by django-allauth
------------------------------------------------------------------

LAVA server can delegate its authentication using the `django_allauth`_
authentication backend.

.. _`django_allauth`: https://django-allauth.readthedocs.io/en/latest/

To enable external provider authentication support you need to set
`AUTH_SOCIALACCOUNT` in your LAVA configuration. Do this by placing a config
snippet in yaml format in the directory ``/etc/lava-server/settings.d``::

  AUTH_SOCIALACCOUNT: "{'gitlab':{'GITLAB_URL': 'https://gitlab.example.com'}}"

This requires django-allauth to be installed manually (e.g., on Debian
you would install the package ``python3-django-allauth``). Afterwards,
run ``lava-server manage migrate``.

Other `authentication providers`_ might require slightly different configuration
or even none at all, e.g. when working with https://gitlab.com::

  AUTH_SOCIALACCOUNT: "{'gitlab':{}}"

.. _`authentication providers`: https://django-allauth.readthedocs.io/en/latest/providers.html

.. note:: To maintain compatibility with LAVA 2021.03 - 2021.09 GitLab
          authentication support can also be enabled by setting
          `AUTH_GITLAB_URL` and `AUTH_GITLAB_SCOPE` directly.

Restart the ``lava-server`` and ``apache2`` services after any changes.

Before you can use external authentication provider, some additional setup steps
need to be performed (following example covers `GitLab OAuth2 authentication`_):

.. _`GitLab OAuth2 authentication`: https://docs.gitlab.com/ce/integration/oauth_provider.html

* In your GitLab instance, you need to add your LAVA installation as an
  **Application**, and enable the ``read_user`` scope.

* The Redirect URI is the URL where users are sent after they authorize with
  GitLab. The form is: `LAVA_URL/accounts/gitlab/login/callback`
  Currently there seems to be a bug in GitLab so the Redirect URI works only
  with **http** protocol.

* After saving the application in GitLab, you will be provided with an
  **Application ID** and a **Secret**.

* In your LAVA administration dashboard, go to **Social Accounts** and
  add a **Social application**. Select **GitLab** as provider and
  enter the credentials you obtained from GitLab as **Client id** and
  **Secret key**.

* While adding the **Social application** make sure to move the sites
  you will use GitLab to authenticate from the **Available sites** to
  **Chosen sites** on the **Sites** tables or ``allauth`` will raise
  an exception saying a matching query does not exist.

.. note:: If SMTP is not set up in LAVA, you can get a 500 Internal server
          error. Login will still work despite the error.

Using Open ID Connect (OIDC) authentication providers
-----------------------------------------------------

LAVA server can be configured to authenticate using OIDC providers
such as Keycloack or Azure AD. The OIDC library used is
`mozilla-django-oidc <https://github.com/mozilla/mozilla-django-oidc>`_.

The library does not come pre-installed and must be installed through
external means. (for example, with ``pip``)

To enable OIDC authorization set ``AUTH_OIDC`` dictionary in one of the
configuration files.

Example::

  ---

  AUTH_OIDC:
    OIDC_RP_CLIENT_ID: "1"
    OIDC_RP_CLIENT_SECRET: "bd01adf93cfb"
    OIDC_OP_AUTHORIZATION_ENDPOINT: "http://testprovider:8080/openid/authorize"
    OIDC_OP_TOKEN_ENDPOINT: "http://testprovider:8080/openid/token"
    OIDC_OP_USER_ENDPOINT: "http://testprovider:8080/openid/userinfo"

See `mozilla-django-oidc settings <https://mozilla-django-oidc.readthedocs.io/en/stable/settings.html>`_
for the list of configuration keys.

One extra setting that LAVA provides is ``LAVA_OIDC_ACCOUNT_NAME``
which sets the login message for OIDC login prompt. For example,
it can be set to ``Azure AD account``. By default it is set to
``Open ID Connect account``.
