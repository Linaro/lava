Quick Developer Setup
=====================

*NOTE:* You should most likely follow the `normal installation instructions </static/docs/deployment-tool.html>`_.
However, these steps can get you a quick setup for local development on
just the dispatcher::

  # get code
  $ sudo apt-get install python-virtualenv
  $ bzr branch lp:lava-dispatcher
  $ cd lava-dispatcher
  # set up virtual environment for development
  $ virtualenv .venv
  $ . .venv/bin/activate
  $ pip install keyring
  $ ./setup.py develop
  # setup configuration
  $ mkdir .venv/etc
  $ cp -r ./lava_dispatcher/default-config/lava-dispatcher .venv/etc/
  $ cat >.venv/etc/lava-dispatcher/devices/qemu01.conf
  device_type = qemu
  $ echo "LAVA_IMAGE_TMPDIR = /tmp" >> .venv/etc/lava-dispatcher/lava-dispatcher.conf

The set up a minimal job like::

    # /tmp/qemu.json
    {
      "timeout": 18000,
      "job_name": "qemu-test",
      "device_type": "qemu",
      "target": "qemu01",
      "actions": [
        {
          "command": "deploy_linaro_image",
          "parameters": {
            "image": "file:///tmp/beagle-nano.img.gz"
            }
        },
        {
          "command": "boot_linaro_image"
        }
      ]
    }

And execute the dispatcher with::

  $ lava-dispatch /tmp/qemu.json

.. seealso:: For writing a new dispatcher job file see :ref:`jobfile`
