# Job definition

The [job definition](../../technical-references/job-definition/job.md) is a `yaml` file that you submit to the LAVA server.
This file is describing everything that LAVA needs to know to run your tests on
a DUT.

## QEMU example

Let's look at this example:

```yaml
--8<-- "jobs/qemu.yaml"
```

## Structure

The job definition is made of:

* `device_type`: requested device-type
* `job_name`: name of the job, sometime called `description`
* `timeouts`: [timeout definition](../../technical-references/job-definition/timeouts.md)
* `priority`: [job priority](../../technical-references/job-definition/job.md#priority)
* `visibility`: [job visibility](../../technical-references/job-definition/job.md#visibility)
* `actions`: list of actions to run

In this definition, we request to run a job called `simple qemu tjob` on a `qemu` DUT.
The job is visible to everyone (including anonymous users).
The job will not run for more than 10 minutes at `medium` priority.

## Actions

`actions` is a list of actions that LAVA will have to execute for the given
job.

Currently, LAVA support four type of actions:

* [command](../../technical-references/job-definition/actions/command.md): run commands on the dispatcher
* [deploy](../../technical-references/job-definition/actions/deploy/index.md): deploy software on the DUT
* [boot](../../technical-references/job-definition/actions/boot.md): boot the DUT
* [test](../../technical-references/job-definition/actions/test.md): run some tests

### Deploy

The deploy action will deploy the software on the DUT, using the method
specified by the `to`.

In this example, we are requesting to deploy to `tmpfs`. The `rootfs` will be
downloaded from the given url.

!!! info "deployment methods"
    LAVA supports many deployment methods. However, only some methods are
    supported by each device-type.

### Boot

The boot action will boot the DUT, using the method specified by the `method`.

In this example, we are requesting to boot `qemu` using the software from
`tmpfs`.

!!! info "boot methods"
    LAVA supports many boot methods. However, only some methods are supported
    by each device-type.

### Test

The test action will run the given tests on the DUT.

In this example, LAVA will download the [test definitions](./test-definition.md) from two git repositories.

!!! info "test methods"
    LAVA supports three test methods that do not depend on the device-type.

--8<-- "refs.txt"
