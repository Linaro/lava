# Running arbitrary code with docker

## Introduction

Testing in LAVA will often require running arbitrary code on the LAVA
dispatcher. Of course, no lab admin would ever allow users running arbitrary
code on their systems, so we need a solution to have users run their arbitrary
code in isolated containers.

This document describes how to use docker to cover the use cases were users
need to run arbitrary code on the lava dispatcher.

## Use case 1: Fastboot deploy from a docker container

Deploying and booting fastboot devices using docker allows you to provide your
own image with a pre-installed fastboot binary, making test jobs faster. To do
this, you just need to add the `docker` section to the fastboot deploy and boot
actions:

```yaml
actions:
# ...
    - deploy:
        to: fastboot
        docker:
            image: my-fastboot-image
        timeout:
            minutes: 15
        images:
            boot:
                url: http://example.com/images/aosp/hikey/boot.img
                reboot: hard-reset
# ...
    - boot:
        method: fastboot
        docker:
            image: my-fastboot-image
        prompts:
            - 'healthd: No battery devices found'
            - 'hikey: '
            - 'console:'
        timeout:
            minutes: 15
```

## Use case 2: Manipulating downloaded images

Some use cases involve downloading different build images and combining them
somehow. Examples include but are not limited to:

* Injecting kernel modules into a rootfs
* Downloading separate kernel/modules/rootfs and combining them in a single
  image for flashing.

This can be achieved using the "**downloads**" deploy method (note
"**downloads**", plural; "**download**"), plus postprocessing instructions:

```yaml
actions:
# ...
    - deploy:
        to: downloads
        images:
            # [...]
            kernel:
                url: http://images.com/.../Image
            modules:
                url: http://images.com/.../modules.tar.xz
            rootfs:
                url: http://images.com/.../rootfs.ext4.gz
                apply-overlay: true
        postprocess:
            docker:
                image: my-kir-image
                steps:
                    - /kir/lava/board_setup.sh hi6220-hikey-r2
```

This will cause all the specified images to be downloaded, and then a docker container
running the specified will be executed.

* The container will have the download directory as the current directory.
    * i.e. the downloaded images will be present in the current directory.
* The steps listed in `steps:` will be executed in order
* Any file modified or created by the steps is left around for later usage.

After the postprocessing fininshes, the resulting images can be used by
specifying their location using the `downloads://` pseudo-URL in a subsequent
deploy action:

```yaml
# ...
    - deploy:
        to: fastboot
        images:
            system:
                rootfs: downloads://rootfs.img
            boot:
                url: downloads://boot.img
```

Those pseudo-URLs are relative to the download directory, from where the
container was executed.

## Use case 3: Running tests from the docker container

To run tests from a docker container, you just need to add a `docker` section
to the well-known LAVA test shell action:

```yaml
# ...
    - test:
        docker:
            image: my-adb-image
        timeout:
        minutes: 5
        definitions:
            - repository:
                # [...]
                from: inline
                path: inline-smoke-test
                name: docker-test
# ...
```

The specified test definitions will be executed inside a container running the
specified image, and the following applies:

* The USB connection to the device is shared with the container, so that you
  can run `adb` and have it connect to the device.
    * For example this can be used in AOSP jobs to run CTS/VTS against the
      device.
* The device connection settings are exposed to the tests running in the
  container via environment variables. For example, assume the given connection
  commands in the device configuration:
    ```jinja
    {% set connection_list = ['uart0', 'uart1'] %}
    {% set connection_commands = {
        'uart0': 'telnet localhost 4002',
        'uart1': 'telnet 192.168.1.200 8001',
        }
    %}
    {% set connection_tags = {'uart1': ['primary', 'telnet']} %}
    ```

    These connection settings will be exported to the container environment as:

    ```shell
    LAVA_CONNECTION_COMMAND='telnet 192.168.1.200 8001'
    LAVA_CONNECTION_COMMAND_UART0='telnet localhost 4002'
    LAVA_CONNECTION_COMMAND_UART1='telnet 192.168.1.200 8001'
    ```

    Of course, for this to work the network addresses used in the configuration
    need to be resolvable from inside the docker container. This requires
    coordination with the lab administration.
* The device power control commands are also exposed in the following
  environment variables: `LAVA_HARD_RESET_COMMAND`, `LAVA_POWER_ON_COMMAND`,
  and `LAVA_POWER_OFF_COMMAND`.

  The same caveat as with the connection commands: any network addresses used
  in such commands need to be accessible from inside the container.

  Note that each of these operations can actually require more than one
  command, in which case the corresponding environment variable will have the
  multiple commands with `&&` between them. Because of this, the safest way to
  run the commands is passing the entire contents of the variable as a single
  argument to `sh -c`, like this:

  ```bash
  sh -c "${LAVA_HARD_RESET_COMMAND}"
  ```

## See also

* LAVA release notes:
    * [2020.01](https://gitlab.com/lava/lava/-/wikis/releases/2020.01)
    * [2020.02](https://gitlab.com/lava/lava/-/wikis/releases/2020.02)
    * [2020.04](https://gitlab.com/lava/lava/-/wikis/releases/2020.04)
* [Improved Android Testing in LAVA with Docker](https://connect.linaro.org/resources/ltd20/ltd20-304/). Talk at Linaro Tech Days 2020.
