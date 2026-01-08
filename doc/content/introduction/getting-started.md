# Getting Started

New to LAVA? You're in the right place. Follow the steps below to get up and
running in minutes.

## Step 1. Install a LAVA instance

A full LAVA instance consists of a LAVA server and one or more LAVA workers.
The server handles job submission, scheduling, live log and result collection.
Workers connect to the server and execute test jobs on physical or virtual
devices.

If you don't have access to an existing LAVA instance, you can set one up
locally using Docker in a few minutes:

[Install LAVA with Docker](../admin/basic-tutorials/instance/install.md#docker)

A worker and two virtual devices are pre-configured for your convenience. Once
the instance is running, verify the following:

- You can [login](http://localhost/accounts/login/)
- Worker [worker0](http://localhost/scheduler/allworkers) is online
- [Devices](http://localhost/scheduler/alldevices/active) `qemu0` and `docker0`
  appear.

Once verified, you're ready to submit your first job.

## Step 2. Submit a LAVA job

A LAVA job is defined in YAML and describes what images to deploy, how to boot
the DUT, and which tests to run, etc.

For your first job, try one of these:

- [Docker job](../admin/basic-tutorials/device-setup/docker.md#submit-a-job) -
  the job creates a Docker container and attaches to the LAVA docker test shell
  and runs inline test definitions that can be easily customized.

- [QEMU job](../user/basic-tutorials/submit.md) — the job boots an image and runs
  test definitions fetched from a Git repository.

For simplicity, submit via the [web interface](../user/basic-tutorials/submit.md#web-interface).

## Step 3. Inspect job output

After your job completes, follow the guide below to review the results and logs
on the job page:

[Understanding job output](../user/basic-tutorials/job-output.md)

## What's next

- [Learn job definition schema](../user/basic-tutorials/job-definition.md)
- [Learn test definition format](../user/basic-tutorials/test-definition.md)

--8<-- "refs.txt"
