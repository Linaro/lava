# LDAP Authentication

LAVA server can be configured to authenticate users via Lightweight Directory
Access Protocol (LDAP). LAVA uses the
[django-auth-ldap](https://django-auth-ldap.readthedocs.io/en/latest/) backend
for LDAP authentication.

## Configuration

LDAP authentication is enabled by setting `AUTH_LDAP_SERVER_URI`. All the
following settings can be placed in `/etc/lava-server/settings.d/01-ldap.yaml`.

```yaml
AUTH_LDAP_SERVER_URI: "ldap://ldap.example.com"
AUTH_LDAP_BIND_DN: ""
AUTH_LDAP_BIND_PASSWORD: ""
AUTH_LDAP_USER_SEARCH: "LDAPSearch('ou=users,dc=example,dc=com', ldap.SCOPE_SUBTREE, '(uid=%(users)')"
AUTH_LDAP_USER_ATTR_MAP:
  first_name: "givenName"
  last_name : "sn"
  email: "mail"
```

Use the following parameter to configure a custom LDAP login page message:

```yaml
LOGIN_MESSAGE_LDAP: "If your email is first.second@example.org then use first.second as your username"
```

Restart [lava-server-gunicorn](../../technical-references/services/lava-server-gunicorn.md)
and [apache2](../../technical-references/services/apache2.md) after any changes.

## User management

To create a superuser, first log in once through the web UI with the target
LDAP `username`, then promote it to superuser:

```shell
sudo lava-server manage authorize_superuser --username <username>
```

Alternatively, create and promote an LDAP user in a single step using `addldapuser`:

```shell
sudo lava-server manage addldapuser --username <username> --superuser
```

An existing local Django user account can be converted to an LDAP user account
without losing data, provided the LDAP username does not already exist in the
LAVA instance:

```shell
sudo lava-server manage mergeldapuser --lava-user <lava_user> --ldap-user <ldap_user>
```
