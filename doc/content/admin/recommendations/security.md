# Security

## ALLOWED_HOSTS

Django requires the allowed hosts to be explicitly set in the LAVA settings, as
a list of host names or IP addresses which LAVA is allowed to use.

By default, only access from the local machine is allowed.

```python
ALLOWED_HOSTS = ["[::1]", "127.0.0.1", "localhost"]
```

To enable remote access, set it to the domain or IP used to access LAVA server,
otherwise, the UI will return HTTP 500.

```yaml
ALLOWED_HOSTS: ["127.0.0.1", "localhost", "lava.example.com"]
```

## SECURE_PROXY_SSL_HEADER

LAVA server is typically deployed behind a reverse proxy (Apache by default) that
performs SSL termination and forwards plain HTTP to a local
[lava-server-gunicorn](../../technical-references/services/lava-server-gunicorn.md)
process.

When SSL is terminated at the reverse proxy, Django may receive requests over
plain HTTP internally. This creates a protocol mismatch that triggers Django’s
CSRF protection, leading to CSRF failures like:

```plain
Forbidden (403)
CSRF verification failed. Request aborted.
```

### LAVA configuration

The recommended fix is to configure LAVA to trust the header provided by your
proxy.

Add this in `/etc/lava-server/settings.d/01-secure.yaml` on your LAVA server:

```yaml
SECURE_PROXY_SSL_HEADER: ["HTTP_X_FORWARDED_PROTO", "https"]
```

!!! note
    Do not work around CSRF errors by adding your site to
    [`CSRF_TRUSTED_ORIGINS`](https://docs.djangoproject.com/en/4.2/ref/settings/#csrf-trusted-origins)
    unless you have a genuine cross-origin or subdomain setup.

!!! danger
    Make sure **ALL** the following are true before setting this:

    - Your LAVA server is strictly served via HTTPS.
    - `lava-server-gunicorn` is bound to `localhost` and is inaccessible from
    the public internet.
    - Your proxy strips the `X-Forwarded-Proto` header from all incoming requests
    and sets its own. This prevents header spoofing.

    For more information, refer to the Django
    [SECURE_PROXY_SSL_HEADER](https://docs.djangoproject.com/en/4.2/ref/settings/#secure-proxy-ssl-header)
    reference.

### Proxy configuration

Ensure your reverse proxy is configured to set the header on every forwarded
request.

#### Apache2

Enable `mod_headers`:

```shell
a2enmod headers
```

Add the directive to your virtual host:

```shell
RequestHeader set X-Forwarded-Proto "https"
```

#### Nginx

Add or verify the following directive within your `location` block. This is
often pre-configured in `/etc/nginx/proxy_params`.

```shell
proxy_set_header X-Forwarded-Proto $scheme;
```

## Cookie

LAVA defaults to secure cookie settings that suitable for HTTPS deployments:

```python
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

With these settings, browsers will only send session and CSRF cookies over
HTTPS. Accessing LAVA over plain HTTP from a non-localhost address will cause
login to fail.

If LAVA is only accessed over HTTP (e.g., a local lab not exposed to the
internet), you can disable the secure cookie requirements:

```yaml
SESSION_COOKIE_SECURE: false
CSRF_COOKIE_SECURE: false
```

!!! note "localhost exemption"
    Modern browsers treat `localhost`, `127.0.0.1`, and `::1` as secure contexts
    even over plain HTTP, so logging in via `http://localhost` may work regardless
    of these settings.

!!! danger
    Do not disable these settings on a server accessible over the internet, as
    it allows session and CSRF tokens to be transmitted in plain text.
