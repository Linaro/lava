# Interactive tests

[Lava-test-shell definitions](../../technical-references/job-definition/actions/test.md#definitions)
need a POSIX shell on the DUT. When the DUT only provides a bootloader shell,
a serial console of a firmware or any other interactive application, use an
[interactive](../../technical-references/job-definition/actions/test.md#interactive)
test action instead.

The interactive test action sends commands to the DUT and matches the output
against the strings given by the test writer. Nothing is deployed on the DUT.

## Testing u-boot

This job stops in the u-boot shell and checks that the network is working:

```yaml
device_type: beaglebone-black
job_name: run tests in U-Boot

timeouts:
  job:
    minutes: 10
  action:
    minutes: 5
  connection:
    minutes: 2
priority: medium
visibility: public

actions:
- boot:
    method: bootloader
    bootloader: u-boot
    commands: []
    prompts:
    - '=>'

- test:
    timeout:
      minutes: 4
    interactive:
    - name: network
      prompts: ['=> ']
      echo: discard
      script:
      - name: dhcp
        command: dhcp
        successes:
        - message: 'DHCP client bound to address (?P<IP>[0-9.]+)'
        failures:
        - message: 'TIMEOUT'
          exception: InfrastructureError
          error: 'dhcp failed'
      - name: ping-server
        command: 'ping {SERVER_IP}'
        successes:
        - message: 'is alive'
        failures:
        - message: 'is not alive'
      - command: 'echo my ip is {IP}'
```

The [bootloader](../../technical-references/job-definition/actions/boot/method-bootloader.md)
boot method interrupts u-boot and waits for the prompt. The test action then:

1. sends `dhcp` and waits for `DHCP client bound to address` or `TIMEOUT`.
   The matched address is saved as `{IP}`. On `TIMEOUT`, the job ends as
   `Incomplete` with an `InfrastructureError`.
2. sends `ping` with the IP of the LAVA worker and records a `pass` or `fail`
   result for `ping-server`. A failure does not stop the job.
3. sends `echo my ip is <ip>` and waits for the prompt.

The results are reported in the `0_network` test suite: `dhcp` and
`ping-server`. The last command has no `name`: no result is recorded, and a
failure of this command would stop the job with a `TestError`.

## Writing good patterns

The interactive test action only knows what the test writer tells it:

* List every failure message that can be printed by a command. Otherwise LAVA
  waits for a success or a prompt until the test action timeout.
* With `successes`, matching a prompt is a failure. Without `successes`,
  matching a prompt is a success.
* The messages are regular expressions matched anywhere in the output:
  `message: 4` matches `14` or `41`. Escape special characters like `(`, `[`
  or `.`, and make the patterns precise enough.
* Use `echo: discard` when the shell echoes the commands, otherwise the
  command itself can match a message.
* Set a short test action timeout: a missing pattern makes the job wait until
  the timeout.

## Combining with other test actions

An interactive test action can be followed by any other action. For instance,
test u-boot, boot Linux and then run lava-test-shell definitions:

```yaml
actions:
- deploy:
    to: tftp
    kernel:
      url: https://example.com/zImage
      type: zimage
    dtb:
      url: https://example.com/am335x-boneblack.dtb
    nfsrootfs:
      url: https://example.com/rootfs.tar.xz
      compression: xz

- boot:
    method: bootloader
    bootloader: u-boot
    commands: []
    prompts:
    - '=>'

- test:
    timeout:
      minutes: 4
    interactive:
    - name: u-boot
      prompts: ['=> ']
      echo: discard
      script:
      - name: version
        command: version
        successes:
        - message: 'U-Boot 20'

- boot:
    method: u-boot
    commands: nfs
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@debian:'

- test:
    timeout:
      minutes: 5
    definitions:
    - name: smoke-tests
      from: git
      repository: https://github.com/Linaro/test-definitions
      path: automated/linux/smoke/smoke.yaml
```

The second boot action resets the device before booting Linux.

## MultiNode

Interactive tests can use the [MultiNode API](../../technical-references/job-definition/protocols.md#api)
with the `lava-send`, `lava-sync`, `lava-wait` and `lava-wait-all` keys. The
values received with `lava-wait` and `lava-wait-all` can be used in the next
commands:

```yaml
- test:
    role:
    - client
    interactive:
    - name: network
      prompts: ['=> ']
      echo: discard
      script:
      - lava-wait: server-ready
      - name: ping-server
        command: 'ping {ip}'
        successes:
        - message: 'is alive'
      - lava-send: client-done
```

The server sends its address with `lava-send server-ready ip=<address>` from a
lava-test-shell definition or an interactive test action.

See the [interactive test reference](../../technical-references/job-definition/actions/test.md#interactive)
for all the options.

--8<-- "refs.txt"
