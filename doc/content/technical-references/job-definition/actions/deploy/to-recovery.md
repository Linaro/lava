# Recovery

The `recovery` deployment method uses commands from the device dictionary and a
test shell to automate recovery mode operations on some DUTs, for example to
flash a new bootloader on a board that can't boot anymore.

```yaml
- deploy:
    to: recovery
    images:
      loader:
        url: https://example.com/l-loader.bin
      ptable:
        url: https://example.com/ptable-linux-8g.img
      fastboot:
        url: https://example.com/fip.bin
    timeout:
      minutes: 10
```

!!! note "Device support"
    Automated recovery requires support by both the admins and the test
    writers. Not all devices can support automated recovery mode.

    In recovery mode, the device may have different identifiers and might no
    longer be unique. This can require a dedicated device-type template and
    only one device of this type on any given worker.

!!! warning "Blind deployment"
    Recovery deployments are **blind**: there is no serial connection, so no
    output is read from the DUT. All the tools and libraries needed to execute
    the recovery operations must be available in the test shell, for example by
    running the test shell in a docker container.

## images

Required. A dictionary of files to download. The keys are free-form names. Each
file supports the common [artifacts](./index.md#artifacts) parameters.

## Job flow

A recovery job is made of the following actions:

1. `deploy` to `recovery`: download the files to flash.
2. `boot` with `method: recovery` and `commands: recovery`: power off the DUT,
   run the `recovery_mode_command` from the device dictionary, then power on the
   DUT.
3. `test`: execute the recovery operations, for example with a vendor flashing
   tool or `fastboot`.
4. `boot` with `method: recovery` and `commands: exit`: power off the DUT, run
   the `recovery_exit_command` from the device dictionary, then power on the
   DUT.

The DUT can then be deployed and booted as usual.

```yaml
- deploy:
    to: recovery
    images:
      script:
        url: https://example.com/hisi-idt.py
      loader:
        url: https://example.com/l-loader.bin
      ptable:
        url: https://example.com/ptable-linux-8g.img
      fastboot:
        url: https://example.com/fip.bin
      nvme:
        url: https://example.com/nvme.img
    timeout:
      minutes: 10

- boot:
    method: recovery
    commands: recovery
    timeout:
      minutes: 5

- test:
    definitions:
    - from: git
      repository: https://gitlab.com/lava/functional-tests.git
      path: testdefs/hikey-6220-recovery.yaml
      name: execute-recovery
    timeout:
      minutes: 10

- boot:
    method: recovery
    commands: exit
    timeout:
      minutes: 5
```

See [recovery boot method](../boot/method-recovery.md).

## Recovery operations

The recovery script may have to wait for the device to appear. As the device
node name may not be predictable, creating a symlink with a known name is
likely to be required.

For example, for the HiKey 6220, the
[recovery mode operations](https://github.com/96boards/documentation/wiki/HiKeyUEFI#user-content-flash-binaries-to-emmc-)
could be executed as steps in the test shell:

```yaml
run:
  steps:
  - find /dev/ -name 'ttyUSB*' -xdev -type c -quit -exec ln -s {} /dev/recovery ';'
  - python hisi-idt.py --img1=l-loader.bin -d /dev/recovery
  # fastboot should wait for the device to reset here
  - fastboot flash ptable ptable-linux.img
  - fastboot flash fastboot fip.bin
  - fastboot flash nvme nvme.img
  # the next boot action takes care of exiting from recovery mode
```

!!! tip "Portable scripts"
    Make these commands **portable** so that the same script can be used to
    flash the device outside of LAVA.

    Make sure that a failure of any command fails the job by using
    [`lava-test-raise`](../../../../user/basic-tutorials/test-definition.md#lava-test-raise):

    ```shell
    command(){
        if [ -n "$(which lava-test-case || true)" ]; then
            echo $2
            $2 && lava-test-case "$1" --result pass || lava-test-raise "$1"
        else
            echo $2
            $2
        fi
    }

    command 'hisi-idt-l-loader' "python ${SCRIPT} --img1=${LOADER} -d /dev/recovery"
    ```

    The first parameter is the test case name (without spaces). The second
    parameter **must** use double quotes so that the variables are substituted.

## Device configuration

The commands to enter and exit recovery mode are defined in the device
dictionary. They usually drive relays connected to the boot mode switches of
the DUT.

```jinja
{% set recovery_mode_command = [
'/usr/local/bin/eth008_control -a 10.15.0.171 -r 1 -s off',
'/usr/local/bin/eth008_control -a 10.15.0.171 -r 2 -s on'] %}
{% set recovery_exit_command = [
'/usr/local/bin/eth008_control -a 10.15.0.171 -r 1 -s on',
'/usr/local/bin/eth008_control -a 10.15.0.171 -r 2 -s off'] %}
```

The device-type template must expose these commands to the `recovery` deploy
method. See `hi6220-hikey-bl.jinja2` and `x15-bl.jinja2` for examples.

Test jobs can terminate early (because of errors or cancellation). Include the
recovery exit commands in the `power_off_command` so that the device is left in
a usable state for the next job:

```jinja
{% set power_off_command = [
'/usr/bin/pduclient --daemon calvin --hostname pdu --command off --port 04',
'sleep 30',
'/usr/local/bin/eth008_control -a 10.15.0.171 -r 1 -s on',
'/usr/local/bin/eth008_control -a 10.15.0.171 -r 2 -s off'] %}
{% set action_timeout_power_off = 60 %}
```

The additional commands may take some time to complete, so the timeout of the
power off action may also need to be extended, as above.

--8<-- "refs.txt"
