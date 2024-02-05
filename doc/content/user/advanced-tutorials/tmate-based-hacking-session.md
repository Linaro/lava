# tmate-based Hacking session

Remote access to a DUT(Device Under Test) in LAVA is supported via a hacking
session. A LAVA hacking session is a special LAVA test job that provides
interactive SSH access to the DUT inside a pre-defined test environment.

Setting up an SSH server on DUT OS could be a pain when package management isn't
supported. Connecting to the DUT SSH server could be another pain when a VPN or
SSH tunnel is needed. This is where tmate comes to the rescue.

[tmate](https://tmate.io/) works by using SSH connections to backend servers.
This means users always connect to the DUT via the backend servers. It also
provides static build for most Linux machine types. Because of its simplicity,
tmate-based LAVA hacking session is recommended. The doc will explain how to use
it in LAVA.

## Prerequisites

To use a tmate-based LAVA hacking session, the following prerequisites must be
in place:

* Both the user and the DUT should have access to `ssh.tmate.io`. It is the CDN
domain name for connecting to the tmate backend servers.
* In the hacking session test definition repository, we included i386, x86_64,
arm32v6, arm32v7, and arm64v8 Linux static tmate builds for convenience. The DUT
you want to use should be one of the supported types.

## Starting a hacking session

A LAVA hacking session is a special LAVA test job with pre-defined deploy, boot,
and test actions. Deploy and boot actions are image and device type relevant. The
test action for starting hacking is always the same.

Refer to the below job example to define your hacking job. The following changes
are required.

* ***Always set job `visibility` to `personal` to avoid leaking SSH access information.***
* ***Provide your SSH public key using the `parameters.PUB_KEY` test parameter. It
is mandatory. tmate session wouldn't be launched if the key is empty or equal
to `None`.***
* Define a meaningful job name.
* Change the device type to the one that you want to use.
* Define the deploy and boot actions for the device type.
* If needed, modify the job level timeout `timeouts.job.minutes`.
* When needed, modify the test action timeout `test.timeout.minutes`.

```yaml
job_name: BBB NFS boot hacking session
device_type: beaglebone-black

timeouts:
  job:
    minutes: 120
  action:
    minutes: 5
  connection:
    minutes: 2

priority: medium
visibility: personal

actions:
- deploy:
    ...

- boot:
    ...

- test:
    timeout:
      minutes: 90
    definitions:
    - repository: https://gitlab.com/lava/hacking-session.git
      from: git
      path: hacking-session-tmate.yaml
      parameters:
          PUB_KEY: "None"
      name: hacking-session
```

## Stopping a hacking session

During a hacking session, your test device can't be used for other jobs. This
will block other users who may want to run tests using the device. So please
stop it just after you finish your work.

* **Cancel** the job using the button on the LAVA job pages. It ends the entire
job immediately.
* **Kill** the tmate process using the command `pkill tmate`. Once the process
is killed, the test will be finished immediately. If no other tests are defined
after the test, the entire job will be finished very quickly.

## SSH-based hacking session

In case you still need the pure SSH-based hacking sessions, see
<https://docs.lavasoftware.org/lava/hacking-session.html>.
