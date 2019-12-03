.. _proxy:

HTTP proxies
============

When running jobs, LAVA is fetching many resources from remote servers
over http.
In some situation or when many jobs are running in parallel, the network
performances could become a bottleneck.

To improve network performances, admins could setup a caching service that will
keep a local version of the resources used by LAVA.

Admin can choice among two kind of caching service:

* generic http proxy like `squid <http://www.squid-cache.org>`_
* specific http cache like `KissCache <https://cache.lavasoftware.org/>`_

Using the HTTP proxy
====================

The dispatcher will use the proxy configured in the HTTP_PROXY environment
variable.

Environment variables are set in:

* ``/etc/lava-server/env.yaml`` for every dispatchers
* ``/etc/lava-server/dispatcher.d/<name>/env.yaml`` for a specific dispatcher

Using the HTTP cache
====================

The dispatcher will use the caching service defined in the dispatcher
configuration in ``/etc/lava-server/dispatcher.d/<name>/dispatcher.yaml``.

Set ``http_url_format_string`` to the url of the local caching service.

.. code-block:: yaml

    http_url_format_string: "https://cache.lavasoftware.org/api/v1/fetch?url=%s"

.. robots:

Handling bots
=============

LAVA has a lot of URLs which may take a lot of work to render on the server. If
automated search bots routinely try to fetch these URLs, the instance can have
performance issues.

LAVA includes a default ``robots.txt`` template which disallows the dynamic
content to reduce the impact on the server. ``static/`` is allowed so that
files like the documentation can be indexed.

To serve a custom ``robots.txt`` from the root of the instance, using Apache,
add an alias at the top of ``/etc/apache2/sites-available/lava-server.conf``::

 Alias /robots.txt /usr/share/lava-server/static/robots.txt

Some bots will handle ``/robots.txt` but some do not (or mishandle options
within the file). To handle this, django supports ``DISALLOWED_USER_AGENTS``
and this is exposed in ``/etc/lava-server/settings.conf``.

.. comment JSON code blocks must be complete JSON, not snippets,
   so this is a plain block.

..

   "DISALLOWED_USER_AGENTS": ["yandex", "bing"],

The values in DISALLOWED_USER_AGENTS are translated into regular expressions
using ``re.compile`` with ``re.IGNORECASE`` so are case-insensitive.

.. note:: Always check your ``robots.txt`` and ``DISALLOWED_USER_AGENTS``
   settings on a local VM before modifying the main instance.
