# Health-Check

An health-check is specific LAVA jobs that is automatically and regularly
scheduled to check the health of DUT.

If for any reason the job fails, the DUT `health` will be set to `Bad` (see
[device health](../state-machine.md#health_1)). The device will not be used
anymore by the scheduler until an admin set the health to either `unknown` or
`good`.

## Reports

Health-check reports are available at
[http://localhost/scheduler/reports](http://localhost/scheduler/reports). The
report shows health-check failures and track the general health of the devices.

There is also a table providing information on the fails checks at
[http://localhost/scheduler/reports/failures?health-checks=1](http://localhost/scheduler/reports/failures?health-checks=1).


## Recommendations

### Golden image

In order to provide constant results, we advice to only use Golden image for
health-checks.

### The infrastructure

As health-checks are normal LAVA jobs, an health-check can test any part of the
infrastructure that is normally used by a LAVA job.

For instance, we recommend to test:

* bootloader methods
* attached devices (hard-drive, probes, ...)
* network access (local or remote servers)

!!! info "lava-test-raise"
    In order to fail a job during the test, call `lava-test-raise <message>`.
    This will return immediately and set the job health to `Incomplete`.

## Configuration file

The health-checks are stored on the server in
`/etc/lava-server/dispatcher-config/health-checks/<name>.yaml`

Admin could update device-type health-check using [lavacli]:

```shell
lavacli device-types health-check set qemu qemu.jinja2
```

!!! info "filename"
    In order to compute the health-check of a DUT, LAVA will look in the device
    dictionary for the `{% extends device-type.jinja2 %}` line. The
    health-check filename is `device-type.yaml`.

--8<-- "refs.txt"
