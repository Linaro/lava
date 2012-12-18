Using the ARM Energy Probe
==========================

The dispatcher includes a `signal handler`_ that allows tests in LAVA
to include power measurement data per test case. Since the functionality
is built into the dispatcher there are really two main things required to
enable this.

 * deployment of a device with the AEP
 * creating jobs to use it

.. _`signal handler`: external_measurement.html

Deployment
----------

Hooking up probes to a specific board are beyond the scope of this document.
However, once a board has a probe hooked up and plugged into the host PC,
the dispatcher can be configured as follows::

  # These options should be added to the device.conf ie:
  # /srv/lava/instances/<INST>/etc/lava-dispatcher/devices/panda01.conf
  # if the defaults are what's needed, then this can be skipped

  # The location of the binary (default=/usr/local/bin/arm-probe)
  arm_probe_binary = /home/doanac/linaro/arm-probe/arm-probe/arm-probe

  # The location of the config file (default=/usr/local/etc/arm-probe-config)
  arm_probe_config = /home/doanac/linaro/arm-probe/config

  # The channels configured for this probe (can be an array default=VDD_VCORE1)
  arm_probe_channels = VDD_VCORE1

Since there may be a mix of device that have AEPs and different configs for
the ones that do, its also recommended to use the LAVA admin interface for
the lava-scheduler to define some tagging scheme that can be used to identify
devices with certain AEP configs. This allows job files to then specify a
tag if it needs AEP or some special AEP config.

Creating a Job File
-------------------

The job is pretty standard and can be read about our `jobfile`_ documentation.
The specific thing needed for an AEP job would be the lava-test-shell action
which would look something like::

   {
        "command": "lava_test_shell",
        "parameters": {
            "testdef_repos": [
              {"bzr-repo": "lp:~doanac/+junk/arm-probe-demo",
               "testdef": "arm-probe.yaml"
              }
            ],
            "timeout": 1800
        }
    }

.. _`jobfile`: jobfile.html

Specifying the Test Definition
------------------------------

The test definition is where the real action happens. The `bzr repo` in the
above example is a great place to look. First start with the `test definition`_.
It goes over how to have the AEP capture data for individual test cases. It also
shows how to add specific parameters to the arm-probe binary in order to do
the type of capture you're needing. The tests themselves, aep-idle.sh and
aep-burn.sh, will run for each AEP data capture.

Upon completion of the test run, the dispatcher will invoke the provided
`postprocess_test_result`_ script so that it can generate things like graphs as it sees
fit to compliment the data normally captured by LAVA.

.. _`bzr repo`: http://bazaar.launchpad.net/~doanac/+junk/arm-probe-demo/files
.. _`test definition`: http://bazaar.launchpad.net/~doanac/+junk/arm-probe-demo/view/head:/arm-probe.yaml
.. _`postprocess_test_result`: http://bazaar.launchpad.net/~doanac/+junk/arm-probe-demo/view/head:/plot.sh
