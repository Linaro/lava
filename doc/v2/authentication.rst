.. index:: user authentication

.. _user_authentication:

Configuring user authentication
===============================

The LAVA frontend is developed using the Django_ web application
framework and user authentication and authorization is based on the
standard `Django auth subsystems`_. This means that it is fairly easy
to integrate authentication against any source for which a Django
backend exists. Discussed below are the tested and supported
authentication methods for LAVA.

.. _Django: https://www.djangoproject.com/
.. _`Django auth subsystems`: https://docs.djangoproject.com/en/dev/topics/auth/

.. note:: The previous OpenID support is not compatible with newer versions of django
   (versions 1.8 or later). As of LAVA version 2016.8, versions of django
   older than 1.8 are not supported, so installing this version will **remove**
   the OpenID support.

Local Django user accounts are supported. When using local Django
user accounts, new user accounts need to be created by Django admin prior
to use.

.. _ldap_authentication:

Using Lightweight Directory Access Protocol (LDAP)
--------------------------------------------------

LAVA server could be configured to authenticate via Lightweight
Directory Access Protocol ie., LDAP. LAVA uses `django_auth_ldap`_
backend for LDAP authentication.

.. _`django_auth_ldap`: http://www.pythonhosted.org/django-auth-ldap/

Your chosen LDAP server is configured using the following parameters
in ``/etc/lava-server/settings.conf`` (JSON syntax)::

  "AUTH_LDAP_SERVER_URI": "ldap://ldap.example.com",
  "AUTH_LDAP_BIND_DN": "",
  "AUTH_LDAP_BIND_PASSWORD": "",
  "AUTH_LDAP_USER_DN_TEMPLATE": "uid=%(user)s,ou=users,dc=example,dc=com",
  "AUTH_LDAP_USER_ATTR_MAP": {
    "first_name": "givenName",
    "email": "mail"
  },

Use the following parameter to set a custom LDAP login page message::

    "LOGIN_MESSAGE_LDAP": "If your Linaro email is first.second@linaro.org then use first.second as your username"

Other supported parameters are::

  "AUTH_LDAP_GROUP_SEARCH": "ou=groups,dc=example,dc=com",
  "AUTH_LDAP_USER_FLAGS_BY_GROUP": {
    "is_active": "cn=active,ou=django,ou=groups,dc=example,dc=com",
    "is_staff": "cn=staff,ou=django,ou=groups,dc=example,dc=com",
    "is_superuser": "cn=superuser,ou=django,ou=groups,dc=example,dc=com"
  }

.. note:: Apart from the above supported parameters, in order to do
          more advanced configuration, make changes to
          ``/usr/lib/python2.7/dist-packages/lava_server/settings/common.py``

Restart ``lava-server`` and ``apache2`` services if this is changed.
