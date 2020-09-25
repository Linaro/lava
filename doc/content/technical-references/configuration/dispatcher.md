# Dispatcher configuration

The dispatcher configuration files allows you to configure some of the beavior
of the dispatchers.

Available files are:

* dispatcher configuration
* environment
* DUT environment

## Dispatcher configuration

Environment configuration file is located on the server in:

* `/etc/lava-server/<hostname>.yaml` old configuration file
* `/etc/lava-server/dispatcher.d/<hostname>/dispatcher.yaml` new configuration file

When loading the configuration, LAVA will look at the new configuration file
and fallback to the old one

```yaml
--8<-- "config/dispatcher.yaml"
```

## Environment

The dispatcher environment is used to set the process environment when spawning
`lava-run`.

Environment configuration file is located on the server in:

* `/etc/lava-server/env.yaml` default, for every dispatchers
* `/etc/lava-server/dispatcher.d/<hostname>/env.yaml` for a specific dispatcher

When loading the configuration, LAVA will look at the dispatcher specific
configuration and fallback to the default configuration.

```yaml
--8<-- "config/env.yaml"
```

## DUT environment

The DUT environment is used to set some environment variable on the DUT when
running tests.

Environment configuration file is located on the server in:

* `/etc/lava-server/env-dut.yaml` default, for every dispatchers
* `/etc/lava-server/dispatcher.d/<hostname>/env-dut.yaml` for a specific dispatcher

When loading the configuration, LAVA will look at the dispatcher specific
configuration and fallback to the default configuration.

The format is the same as for the environment file.

--8<-- "refs.txt"
