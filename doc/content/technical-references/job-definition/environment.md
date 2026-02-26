# Environment

The job can define environment variables for the device. The variables are made
available in the test shell environment and can be referenced in test scripts then.

Environment variables defined in the job will override environment variables of
the same name defined in the
[device dictionary](../configuration/device-dictionary.md#device).

## Signal node

```yaml
environment:
  FOO: bar
  BAR: baz
```

## Multinode

For multinode jobs, the environment has to be defined for each multinode role
separately:

```yaml
protocols:
  lava-multinode:
    roles:
      node_a:
        environment:
          FOO: bar
      node_b:
        environment:
          BAR: baz
```
