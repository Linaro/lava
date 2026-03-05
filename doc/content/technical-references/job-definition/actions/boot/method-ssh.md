# SSH

The `ssh` boot method connects the LAVA worker to an already running device over
SSH. The device must be booted up and reachable at the address configured in
the [SSH device dictionary](../../../configuration/device-dictionary.md#ssh).

```yaml
- boot:
    method: ssh
    prompts:
    - 'root@device:~#'
```

The boot action:

1. Opens an SSH session from the worker to the device.
2. Copies the LAVA test overlay to the device using SCP.
3. Waits for the expected shell prompt.
4. Unpacks the overlay on the device for test execution.

## prompts

See [prompts](./common.md#prompts)

## Job example

```yaml
job_name: SSH job example
device_type: ssh
visibility: public

timeouts:
  job:
    minutes: 5
  action:
    minutes: 2

actions:
- deploy:
    to: ssh
    os: debian

- boot:
    method: ssh
    prompts:
    - 'root@device:~#'

- test:
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: test-definition-example
        run:
          steps:
          - lava-test-case run-uname-a --shell uname -a
          - lava-test-case check-os-id --shell 'cat /etc/os-release | grep "ID=debian"'
      path: inline/test-definition-example.yaml
      name: test-suite-example
```
