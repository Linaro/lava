# Environment

The job can define environment variables for the device. The variables are made
available in the test shell environment and can be referenced in test scripts then.

Environment variables defined in the job will override environment variables of
the same name defined in the
[device dictionary](../configuration/device-dictionary.md#device).

LAVA also writes a small set of metadata into the same overlay `environment`
file. These `LAVA_*` variables are sourced by the test shell after the job and
device environment, so they take precedence if a name clashes.

Do not confuse these with the bootloader placeholders such as `{LAVA_JOB_ID}`
documented in [boot common](./actions/boot/common.md). Those are substituted
into boot commands on the dispatcher, not exported into the DUT test shell.

## LAVA-injected variables

| Variable | Description |
| --- | --- |
| `LAVA_JOB_ID` | Numeric job ID assigned by the scheduler |
| `LAVA_DISPATCHER_IP` | IP address of the LAVA worker running this job |
| `LAVA_DISPATCHER_PREFIX` | Optional dispatcher `prefix` from the worker config |
| `LAVA_JOB_TAGS` | Comma-separated [job tags](./job.md#tags). Empty when the job requested none |
| `LAVA_DEVICE_HOSTNAME` | Hostname of the assigned device, if present in the device config |
| `LAVA_DEVICE_TYPE` | Device type of the assigned device, if present in the device config |
| `HTTP_CACHE` | Dispatcher `http_url_format_string`, when configured |

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
