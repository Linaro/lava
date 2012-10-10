Deploy Android
==============

Here's an example of a job file that will deploy and boot an Android image::

    {
      "job_name": "android_test",
      "target": "panda01",
      "timeout": 18000,
      "actions": [
        {
          "command": "deploy_linaro_android_image",
          "parameters":
            {
              "boot": "http://releases.linaro.org/12.09/android/leb-panda/boot.tar.bz2",
              "system": "http://releases.linaro.org/12.09/android/leb-panda/system.tar.bz2",
              "data": "http://releases.linaro.org/12.09/android/leb-panda/userdata.tar.bz2"
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

Installing Panda Binary Blobs
-----------------------------

Some Android builds for Panda require a binary blob to be installed. This can
be done by adding the ``android_install_binaries`` after the
``deploy_linaro_android_image``::

        {
          "command": "deploy_linaro_android_image",
          "parameters":
            {
              "boot": "http://releases.linaro.org/12.09/android/leb-panda/boot.tar.bz2",
              "system": "http://releases.linaro.org/12.09/android/leb-panda/system.tar.bz2",
              "data": "http://releases.linaro.org/12.09/android/leb-panda/userdata.tar.bz2"
            }
        },
        {
          "command": "android_install_binaries"
        }
