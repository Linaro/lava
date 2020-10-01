# Proxy

When running jobs, LAVA is fetching many resources from remote servers over
http or https. In some situation or when many jobs are running in parallel, the
network performances could become a bottleneck.

To improve network performances, you could setup a caching service that will
keep a local version of the resources used by LAVA.

You can choose among two kind of caching service:

* generic http proxy like [squid][squid]
* http caching service like [KissCache][KissCache]

## SQUID

SQUID is a well know caching proxy that will cache resources available over
http only.

!!! warning "SQUID and https"
    Configuring SQUID to cache https resources is an advance topic.
    If you need to cache https resources, you should have a look at
    [KissCache](#kisscache).

LAVA dispatcher uses the proxy configured in the `HTTP_PROXY` environment
variable.

!!! info "dispatcher environment"
    Environment variables are set in:

    * `/etc/lava-server/env.yaml` for every dispatchers
    * `/etc/lava-server/dispatcher.d/<name>/env.yaml` for a specific dispatcher

    Read [the documentation](../../technical-references/configuration/dispatcher.md)
    for more information.

??? tip "DUT environment"
    LAVA can also set the environment variable on the DUT.

    Read [the documentation](../../technical-references/configuration/dispatcher.md)
    for more information.

## KissCache

KissCache is a simple and stupid caching server.

KissCache is able to fetch and cache remote resources over `http` and `https`.
It can also download and stream the resource to many clients in parallel.

In order to use KissCache, users should prefix the resources's URLs by the
KissCache instance URL.

LAVA will use the KissCache instance specified in the dispatcher configuration:
```yaml
http_url_format_string: "https://kisscache-instance/api/v1/fetch?url=%s"
```

--8<-- "refs.txt"
