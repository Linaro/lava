Deploy Pre-Built Image
======================

Here's a minimal job that will deploy and boot a pre-built image::

    {
      "job_name": "panda-prebuilt",
      "target": "panda01",
      "timeout": 18000,
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters":
            {
              "image": "http://releases.linaro.org/12.09/ubuntu/leb-panda/lt-panda-x11-base-precise_ubuntu-desktop_20120924-329.img.gz"
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

