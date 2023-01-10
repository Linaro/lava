# Running arbitrary code with docker

## Introduction

Testing in LAVA will often require running arbitrary code on the LAVA
dispatcher. Of course, no lab admin would ever allow users running arbitrary
code on their systems, so we need a solution to have users run their arbitrary
code in isolated containers.

LAVA originally supported the use of [LXC](https://linuxcontainers.org/)
containers. LXC is a great tool, but the way they are used in LAVA is complex
and error prone. Starting with the 2020.04 release, LAVA now supports running
the same operations that used to require LXC under docker, in a streamlined and
simpler way.

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
"**downloads**", plural; "**download**" singular is used by the legacy LXC
support), plus postprocessing instructions:

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


## Migrating from LXC to Docker

Migrating jobs using LXC to use docker most of the time involves deleting the
LXC boot and deploy actions, and adapting the test ones. This section provides
a few migration examples.

### AOSP CTS/VTS

These jobs deploy images and boot the device via fastboot, then run adb from
the dispatcher, connecting to the device. adb used to run from an LXC
container.

* [Original job](running-arbitrary-code-with-docker/cts-lxc.yaml)
* [New job](running-arbitrary-code-with-docker/cts-docker.yaml)

Let's look an annotated version of the difference between the original and the
new job, where the actions taken are explicitly explained.

```diff
--- cts-lxc.yaml	2020-04-06 14:49:20.646012743 -0300
+++ cts-docker.yaml	2020-04-06 15:09:23.493288149 -0300
@@ -31,50 +31,13 @@
   ARTIFACTORIAL_TOKEN: 3a861de8371936ecd03c0a342b3cb9b4
   AP_SSID: LAVATEST-OEM
   AP_KEY: NepjqGbq
-protocols:
-  lava-lxc:
-    name: lxc-test
-    distribution: ubuntu
-    release: bionic
-    arch: amd64
-    verbose: true
```

1) Remove the **protocols:** section.

```diff
 actions:
 - deploy:
-    namespace: tlxc
-    timeout:
-      minutes: 10
-    to: lxc
-    packages:
-    - wget
-    - unzip
-    - git
-    - trace-cmd
-    os: ubuntu
-- boot:
-    namespace: tlxc
-    prompts:
-    - root@(.*):/#
-    - :/
-    timeout:
-      minutes: 5
-    method: lxc
-- test:
-    namespace: tlxc
-    timeout:
-      minutes: 10
-    definitions:
-    - repository: https://git.linaro.org/qa/test-definitions.git
-      from: git
-      path: automated/linux/android-platform-tools/install.yaml
-      name: install-android-platform-tools-r2800
-      parameters:
-        LINK: https://dl.google.com/android/repository/platform-tools_r28.0.0-linux.zip
```

2) Remove the deploy, boot and test sections for the LXC containers, i.e. the
ones that have **namespace: tlxc** or similar. 

```diff
-- deploy:
     timeout:
       minutes: 15
     to: fastboot
-    namespace: target
-    connection: lxc
+    docker:
+      image: terceiro/android-platform-tools
     images:
       ptable:
         url: http://images.validation.linaro.org/snapshots.linaro.org/96boards/reference-platform/components/uefi-staging/69/hikey/release/ptable-aosp-8g.img
@@ -92,14 +55,9 @@
       vendor:
         url: http://testdata.linaro.org/lkft/aosp-stable/android-lcr-reference-hikey-q/11//vendor.img.xz
         compression: xz
-    protocols:
-      lava-lxc:
-      - action: fastboot-deploy
-        request: pre-power-command
-        timeout:
-          minutes: 2
```

3) For the device deploy action, drop **namespace: target** and **connection:
lxc**, and replace them with the **docker** section, specifying which image to
use. Drop the **protocols:** section.


```diff
 - boot:
-    namespace: target
+    docker:
+      image: terceiro/android-platform-tools
     prompts:
     - root@(.*):/#
     - hikey:/
@@ -109,7 +67,8 @@
       minutes: 15
     method: fastboot
```

4) For the device boot action, drop the **namespace: target** (which is now
implied and not necessary) and add the **docker** section.

```diff
 - test:
-    namespace: tlxc
+    docker:
+      image: terceiro/android-platform-tools
     timeout:
       minutes: 20
     definitions:
@@ -129,7 +88,8 @@
           - lava-test-case "android-boot-screepcap" --shell adb shell screencap -p
             /data/local/tmp/screencap.png
 - test:
-    namespace: tlxc
+    docker:
+      image: terceiro/android-platform-tools
     timeout:
       minutes: 360
     definitions:
```

5) For each of the test actions that previously ran in the LXC container, drop
**namespace: tlxc**, and add the **docker** section as those will now run under
docker.

### Example 2: LKFT-style OpenEmbedded jobs

This job downloads images, postprocesses them using
[kir](https://github.com/Linaro/kir), then deploys them using fastboot, then
boots the device using fastboot, turns the USB OTG port off so the USB host on
the device work, then runs normal tests on the device.

* [Original job](running-arbitrary-code-with-docker/hikey-lkft-like-lxc.yaml)
* [New job](running-arbitrary-code-with-docker/hikey-lkft-like-docker.yaml)

Annotated diff:

```diff

--- hikey-lkft-like-lxc.yaml	2020-04-15 09:24:07.370767885 -0300
+++ hikey-lkft-like-docker.yaml	2020-04-15 09:24:07.370767885 -0300
@@ -11,62 +11,13 @@
 visibility: public
 metadata:
   source: https://lkft.validation.linaro.org/scheduler/job/1295576/definition
-protocols:
-  lava-lxc:
-    name: lxc-target
-    template: debian
-    distribution: debian
-    release: bullseye
-    arch: amd64
-    mirror: http://deb.debian.org/debian
 
```

1) Drop the **protocols:** session.


```diff
 actions:
 
   - deploy:
-      namespace: tlxc
-      timeout:
-        minutes: 15
-      to: lxc
-      packages:
-        - wget
-        - unzip
-        - android-tools-fsutils
-        - curl
-        - cpio
-        - file
-        - git
-        - libguestfs-tools
-        - linux-image-amd64
-        - mkbootimg
-        - xz-utils
-        - --no-install-recommends
-      os: debian
-
-  - boot:
-      namespace: tlxc
-      prompts:
-      - root@(.*):/#
-      timeout:
-        minutes: 5
-      method: lxc
-
-  - test:
-      namespace: tlxc
-      timeout:
-        minutes: 10
-      definitions:
-      - repository: https://github.com/Linaro/test-definitions.git
-        from: git
-        path: automated/linux/android-platform-tools/install.yaml
-        name: install-android-platform-tools-r2800
-        parameters:
-          LINK: https://dl.google.com/android/repository/platform-tools_r28.0.0-linux.zip
-
```

2) Drop the **deploy**, **boot** and **test** actions used to provision the LXC
container.


```diff
-  - deploy:
       timeout:
         minutes: 40
-      to: download
-      namespace: target
+      to: downloads
       images:
         ptable:
           url: http://localhost:8888/oe/hikey-4.9/ptable-linux-8g.img
@@ -82,73 +33,50 @@
           url: http://localhost:8888/oe/hikey-4.9/rpb-console-image-lkft-hikey-20200205141751-9.rootfs.ext4.gz
           apply-overlay: true
       os: oe
-
```

3) Switch the deployment method from **download** (singular) to **downloads**
(plural); remove the **namespace::** field.


```diff
-  - test:
-      namespace: tlxc
-      timeout:
-        minutes: 60
-      definitions:
-      - from: inline
-        name: kir
-        path: inline/kir.yaml
-        repository:
-          metadata:
-            description: Squash kernel, dtb and modules into rootfs
-            format: Lava-Test Test Definition 1.0
-            name: resize-rootfs
-          run:
-            steps:
-            - pwd
-            - cd /lava-lxc
-            - git clone -b 20200115 https://github.com/linaro/kir.git
-            - ./kir/lava/board_setup.sh hi6220-hikey
+      postprocess:
+        docker:
+          image: terceiro/kir
+          steps:
+            - /kir/lava/board_setup.sh hi6220-hikey-r2
 
```

4) Replace the LXC test action that postprocesses the downloaded images with a
**postprocess:** section in the **downloads** deploy action.


```diff
   - deploy:
       timeout:
         minutes: 40
       to: fastboot
-      namespace: target
+      docker:
+        image: terceiro/kir
       images:
         ptable:
-          url: lxc:///ptable-linux-8g.img
+          url: downloads://ptable-linux-8g.img
           reboot: hard-reset
         boot:
-          url: lxc:///boot.img
+          url: downloads://boot.img
           reboot: hard-reset
         system:
-          url: lxc:///rpb-console-image-lkft.rootfs.img
+          url: downloads://rpb-console-image-lkft.rootfs.img
           apply-overlay: true
       os: oe
-      protocols:
-        lava-lxc:
-        - action: fastboot-deploy
-          request: pre-power-command
-          timeout:
-            minutes: 2
 
```

5) On the device deploy, drop **namespace: target** (which is now implied); add
the **docker** section indicating which image to run fastboot from; replace
**lxc:///** with **downloads://** in the image URLs; drop the **protocols:**
section, as the `pre-power-command` is implied on fastboot deploys.


```diff
   - boot:
-      namespace: target
+      docker:
+        image: terceiro/kir
       method: grub
       commands: installed
       auto_login:
@@ -142,12 +74,10 @@
         - root@(.*):[/~]#
       timeout:
         minutes: 10
-      protocols:
-        lava-lxc:
-        - action: auto-login-action
-          request: pre-os-command
-          timeout:
-            minutes: 2
+
+  - command:
+      # turns off USB OTG
+      name: pre_os_command
 
   - test:
       timeout:
```

6) On the device boot action, drop the **namespace:** section, now implied; add
the **docker:** section to specify which image to run fastboot from; drop the
**protocols:** session, and replace it with a **command** action. For this job,
it's necessary to to keep the `pre_os_command` - it will turn off the USB OTG
connection and allow the device to use the USB host for e.g. wired networking.

Note that the diff ends here. The test action, since it runs on the device,
remains unchanged.

## See also

* LAVA release notes:
    * [2020.01](https://git.lavasoftware.org/lava/lava/-/wikis/releases/2020.01)
    * [2020.02](https://git.lavasoftware.org/lava/lava/-/wikis/releases/2020.02)
    * [2020.04](https://git.lavasoftware.org/lava/lava/-/wikis/releases/2020.04)
* [Improved Android Testing in LAVA with Docker](https://connect.linaro.org/resources/ltd20/ltd20-304/). Talk at Linaro Tech Days 2020.
