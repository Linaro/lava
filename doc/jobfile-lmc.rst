Deploy Using linaro-media-create
================================

Here's an example of a job file that will deploy an image on a target based on
a hardware pack and root filesystem from Linaro::

    {
      "job_name": "panda-lmc",
      "target": "panda01",
      "timeout": 18000,
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters":
            {
              "rootfs": "http://releases.linaro.org/12.09/ubuntu/precise-images/nano/linaro-precise-nano-20120923-417.tar.gz",
              "hwpack": "http://releases.linaro.org/12.09/ubuntu/leb-panda/hwpack_linaro-lt-panda-x11-base_20120924-329_armhf_supported.tar.gz"
            }
        },
        {
          "command": "boot_linaro_image"
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

