# Health-Check

A health-check is a specific LAVA job that is automatically and regularly
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
    In order to fail a job during the test, call [`lava-test-raise <message>`](../../user/basic-tutorials/test-definition.md#lava-test-raise).
    This will return immediately and set the job health to `Incomplete`.

## Configuration file

The health-checks are stored on the server in
`/etc/lava-server/dispatcher-config/health-checks/<name>.yaml`

By default, LAVA creates device-types with a routine health-check frequency of
24 hours. Admins can change this default for an instance by setting
`HEALTH_FREQUENCY_HOURS` in one of the [LAVA settings files](../../admin/basic-tutorials/instance/configure.md#configuration-files), for example:

```yaml
HEALTH_FREQUENCY_HOURS: 168
```

Admin could update device-type health-check using [lavacli]:

```shell
lavacli device-types health-check set qemu qemu.jinja2
```

!!! info "filename"
    In order to compute the health-check of a DUT, LAVA will look in the device
    dictionary for the `{% extends device-type.jinja2 %}` line. The
    health-check filename is `device-type.yaml`.

## Secrets

A health-check may need credentials, for instance to authenticate against a
service or to download a private artifact.

As for any other job, a health-check can use [secrets](../job-definition/job.md#secrets)
and refer to a remote artifact token by name, so the token value never appears
in the health-check definition. LAVA resolves the token names against the
remote artifact tokens of the **job submitter**. Health-checks are submitted
automatically by LAVA using the `lava-health` service account, so the remote
artifact tokens are resolved from this user.

The `lava-health` account cannot log in, so its tokens cannot be modified
through the usual profile page. Admins should add them from the Django admin
interface: edit the `lava-health` user and add the tokens in the
**Remote artifacts auths** form, filling the `Name` and `Token` fields.

!!! warning "REST API"
    The `/api/v0.2/remote-artifact-tokens/` endpoint always operates on the
    authenticated user. Since the `lava-health` user cannot log in, this
    endpoint cannot be used to manage its tokens; use the Django admin
    interface instead.

For example, add a token named `example-token-reference` to the `lava-health`
user, then refer to it from the health-check definition:

```yaml
job_name: example health check

secrets:
  API_TOKEN: example-token-reference

actions:
- deploy:
    # ...

- boot:
    # ...

- test:
    definitions:
    - from: inline
      name: example
      path: inline/example.yaml
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: example
        run:
          steps:
          - . /lava-*/secrets
          - curl -H "Authorization: Bearer ${API_TOKEN}" https://example.com/check
```

LAVA replaces `example-token-reference` with the real token value when the job
runs; the definition shown to users keeps the token name.

### Downloading a private artifact

The `secrets` block is only exported to the test shell, so it cannot be used to
authenticate a download. Use an
[authenticated download](../job-definition/actions/deploy/index.md#authenticated-downloads)
instead: token names used in the artifact `headers` are resolved from the
`lava-health` user, just like the ones in `secrets`.

--8<-- "refs.txt"
