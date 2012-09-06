.. _jobfile:

Writing a Dispatcher Job File
*****************************

Linaro Ubuntu Images
====================

Here's an example of a job file to run the stream test on an Ubuntu based Linaro Image. Stream is a small, fast test, and great for testing that everything works OK::

    {
      "job_name": "foo",
      "target": "panda01",
      "timeout": 18000,
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters":
            {
              "rootfs": "http://snapshots.linaro.org/11.05-daily/linaro-developer/20110208/0/images/tar/linaro-n-developer-tar-20110208-0.tar.gz",
              "hwpack": "http://snapshots.linaro.org/11.05-daily/linaro-hwpacks/panda/20110208/0/images/hwpack/hwpack_linaro-panda_20110208-0_armel_supported.tar.gz"
            }
        },
        {
          "command": "lava_test_install",
          "parameters":
            {
                "tests": ["stream"]
            }
        },
        {
          "command": "boot_linaro_image"
        },
        {
          "command": "lava_test_run",
          "parameters":
            {
              "test_name": "stream"
            }
        },
        {
          "command": "submit_results",
          "parameters":
            {
              "server": "http://localhost/lava-server/RPC2/",
              "stream": "/anonymous/test/"
            }
        }
      ]
    }

Linaro Android Images with new kernel
=====================================

This job file uses a boot partition tarball specified by "pkg"
directly, it will replace the files in tarball to boot partition::

    {
      "job_name": "android_new_kernel",
      "target": "panda01",
      "timeout": 18000,
      "actions": [
        {
          "command": "deploy_linaro_android_image",
          "parameters":
            {
              "boot": "https://android-build.linaro.org/jenkins/job/linaro-android_leb-panda/61/artifact/build/out/target/product/pandaboard/boot.tar.bz2",
              "system": "https://android-build.linaro.org/jenkins/job/linaro-android_leb-panda/61/artifact/build/out/target/product/pandaboard/system.tar.bz2",
              "data": "https://android-build.linaro.org/jenkins/job/linaro-android_leb-panda/61/artifact/build/out/target/product/pandaboard/userdata.tar.bz2",
              "pkg": "https://android-build.linaro.org/jenkins/job/linaro-android_leb-panda/171/artifact/build/out/target/product/pandaboard/boot.tar.bz2"
            },
          "metadata":
            {
              "rootfs.type": "android",
              "rootfs.build": "61"
            }
        },
        {
          "command": "boot_linaro_android_image"
        },
        {
          "command": "lava_android_test_install",
          "parameters":
            {
                "tests": ["0xbench"]
            }
        },
        {
          "command": "lava_android_test_run",
          "parameters":
            {
              "test_name": "0xbench"
            }
        },
        {
          "command": "submit_results_on_host",
          "parameters":
            {
              "server": "http://validation.linaro.org/lava-server/RPC2/",
              "stream": "/anonymous/android-panda01-basic/"
            }
        }
      ]
    }


Linaro Android Images
=====================

Here's an example showing how to run 0xbench on a Linaro Android image::

    {
      "job_name": "android_monkey_test2",
      "target": "panda01",
      "timeout": 18000,
      "actions": [
        {
          "command": "deploy_linaro_android_image",
          "parameters":
            {
              "boot": "https://android-build.linaro.org/jenkins/job/gerrit-bot_pandaboard/12/artifact/build/out/target/product/pandaboard/boot.tar.bz2",
              "system": "https://android-build.linaro.org/jenkins/job/gerrit-bot_pandaboard/12/artifact/build/out/target/product/pandaboard/system.tar.bz2",
              "data": "https://android-build.linaro.org/jenkins/job/gerrit-bot_pandaboard/12/artifact/build/out/target/product/pandaboard/userdata.tar.bz2"
            },
          "metadata":
            {
              "rootfs.type": "android",
              "rootfs.build": "12"
            }
        },
        {
          "command": "boot_linaro_android_image"
        },
        {
          "command": "lava_android_test_install",
          "parameters":
            {
                "tests": ["0xbench"]
            }
        },
        {
          "command": "lava_android_test_run",
          "parameters":
            {
              "test_name": "0xbench"
            }
        },
        {
          "command": "submit_results_on_host",
          "parameters":
            {
              "server": "http://validation.linaro.org/lava-server/RPC2/",
              "stream": "/anonymous/lava-android-leb-panda/"
            }
        }
      ]
    }

