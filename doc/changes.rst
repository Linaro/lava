Version History
***************

.. _version_0_32:

Version 0.32
============

* Unreleased

.. _version_0_31:

Version 0.31
============

* Use Launcher information from logcat to check for display of home screen.
* Remove broken attempt to attach serial log to lava test run.

.. _version_0_30:

Version 0.30
============
* fillout log_lineno for lava-test-shell results
* make fastmodel config files easier to manage
* configglue warning fixes
* keep old results directory around in lava-test-shell to help debug

.. _version_0_29:

Version 0.29
============
* fix to ARM Energy Probe post processing logic
* enable networking in FastModel v8
* add --target override parameter for "lava dispatch"
* fix timeout bug in lava_test_shell action
* foundational changes to get ready for Galaxy Nexus support
* sdmux device support
* partition file layout update for panda-android

.. _version_0_28:

Version 0.28
============
* lava-test-case should not return non-zero exit code for --shell false
* Replace all usage of shutil.rmtree with a shell call to `rm -rf`
* add support for ARM Energy Probe

.. _version_0_27:

Version 0.27
============
* bug fix: include lava-test-run-attach
* improve serial console input delay

.. _version_0_26:

Version 0.26
============
* improve uinitrd logic for master.py and android
* allow more options about what an android 'boot' means
* sync on device-types that were actually in use in the lab

.. _version_0_25:

Version 0.25
============
* signal handlers can be implemented as shell scripts
* various lava-test-shell bug fixes

.. _version_0_24_1:

Version 0.24.1
==============
* lava-test-shell related fixes

.. _version_0_24:

Version 0.24
============
* add a new "lava devices" command
* fixed some configglue related warnings
* some bug fixes for signals
* improve android partition mount logic

.. _version_0_23:

Version 0.23
============
* signal support
* fix pipe draining issue causing 100% cpu consumption with CTS
* fix bug where ctrl-c causes exception
* job priority support
* YAML test def can be specified in a git/bzr repo

.. _version_0_22:

Version 0.22
============
* refactor fastmodel implementation to not require code changes for new products
* simplify power_off/sync logic in targets
* boot_options improvements
* extract_tarball API added to target
* change lava-test-shell defintion format to be YAML
* allow test definitions to use a default parsing pattern

.. _version_0_21:

Version 0.21
============
* allow boot to master logic to retry a few times before exiting with error
* move lava-test-shell test def format to use YAML
* CTS fix
* fix unicode issue in new usage of python's tarfile lp:1071279

.. _version_0_20_1:

Version 0.20.1
==============
* fixed prompt issue on Android that was causing timeouts

.. _version_0_20:

Version 0.20
============
* Support device version for qemu and rtsm.
* Add dummy_deployment action.
* Add mkdir -p /mnt/lava/boot to android deployment.

.. _version_0_19_1:

Version 0.19.1
==============
* fixed a packaging issue with lava_test_shell files

.. _version_0_19:

Version 0.19
============
* Change to using configglue to manage our configuration
* transition to new "target" based API
* add new "lava-test-shell" for black-box style test support
* add v8 FoundationsModel support to fastmodel.py

.. _version_0_18:

Version 0.18
============
* fix issue with /etc/resolv.conf
* removed unused/unsupported action attributes: pkg and kernel_matrix

.. _version_0_17_2:

Version 0.17.2
==============
* fixed sd card issue for Android Panda JellyBean

.. _version_0_17.1:

Version 0.17.1
============
* regression bug fix for ADB connections in FastModels
* bug lp:1032467
* don't leak LAVA access token into logfile

.. _version_0_17:

Version 0.17
============
* fixes for FastModel support
* URL mapping feature
* boot support for Open Embedded images

.. _version_0_16:

Version 0.16
============
* Fix #1028512, provide test image hostname custom option: tester_hostname.
* Fix #1019630, possibility to set proxy error when sending serial port command.
* Add support for Ubuntu images to FastModel client
* Allow clients to handle custom boot options

.. _version_0_15_2:

Version 0.15.2
==============
* made consistent downloading and temp file creation logic to help prevent disk leakage

.. _version_0_15_1:

Version 0.15.1
==============
* fixed a bug causing cache leak and pre-built image test failure

.. _version_0_15:

Version 0.15
============
* support for /sdcard partition for Android
* change vmalloc args for snowball
* more cache logic cleanup
* fastmodel client bug fixes
* change over to use disablesuspend.sh script

.. _version_0_14:

Version 0.14
============
* FastModel support for Android
* FastModel boot support for Ubuntu
* QEMU device updates
* Improved timeout handling

.. _version_0_13:

Version 0.13
============

* Add all repositories specified in the add_apt_repository command.
* Increase the number of retries and decrease the wait time in
  _deploy_tarball_to_board
* Make sure all download code uses the configured proxy, and enable
  custom cookies to be set when downloading.
* Reboot after a lava-android-test times out.
* Make lava-dispatch invoke lava dispatch, and make the latter's
  logging setup match the formers
* Fix lava_android_test_run.test_name to not error when an option is
  passed to lava_android_test_run in the JSON.

.. _version_0_12:

Version 0.12
============

* Another attempt to detect a stuck port on an ACS6000.
* Do not crash when wait_for_home_screen times out.

.. _version_0_11:

Version 0.11
============

* Watch for various messages from the connection_command that indicate
  how successful the connection attempt has been, and do various
  things in response.

.. _version_0_10:

Version 0.10
============

* Add support for a pre_connect_command that will be executed before
  connection_command.
* Add 'lava connect' and 'lava power-cycle' commands.

.. _version_0_9:

Version 0.9
===========

* Make retrying deployment if failed more robust.
* Log a message when submit_results fails.

Version 0.8
===========

* Fixed reboot issues
* Skip raising exception on the home screen has not displayed for health check jobs
* Retry deployment if failed.
* Allow lava-test-install action to install extra debs.
* Allow installing lava-test from a deb.
* Support running tests with monkeyrunner.

.. _version_0_7_1:

Version 0.7.1
=============

* Increase the timeout around the shell commands to set up the proxy in the
  test image.
* Make the wget part of the wget|tar operations slightly more verbose.
* Do not fetch the test images to the board through the proxy.

.. _version_0_7:

Version 0.7
===========

* Use squid proxy for caching mechanism
* Run all lava-test install commands with a wrapper that catches errors.
* Support tags in the job file.
* Kill the process we're using to talk to the board on dispatcher exit.
* Update the schema for add_apt_repository to match usage, making the action
  usable again.

.. _version_0_6:

Version 0.6 (Milestone 12.04)
=============================

* Merge 0.5.12 bugfix release
* Config options for interrupting boot process
* Fix package dependency on python-keyring
* Cache rootfs and boot tarballs

.. _version_0_5_12:

Version 0.5.12
==============

* Increase timeout for rootfs deployment to 5 hours (18000 seconds).
  This should help in working with vexpress.

.. _version_0_5_11:

Version 0.5.11
==============
* Fixed boot android image problem caused by changing of init.rc file.
* Make sure to look on device for bundles even if all test run steps fail.
* Use the correct lmc_dev_arg for beagle-xm
* Add qemu_drive_interface configuration option for the LAVA QEMU client.

.. _version_0_5_10:

Version 0.5.10
==============
* Omit the commands we send to the board from the log (as this output is
  invariably echoed back and so was ending up in the output twice)

* Convert the dispatcher to LAVA commnand. It can now be called from the shell
  by running ``lava dispatch``. The old command line interface
  ``lava-dispatch`` is now deprecated and will be removed in the 0.8 release in
  three months.

.. _version_0_5_9:

Version 0.5.9
=============
* Make the validation of the job file that happens before a job starts
  more rigorous.
* Change snowball boot arg vmalloc=300M

.. _version_0_5_8:

Version 0.5.8
=============
* Changes for virtual express support:
  * Add in a standard vexpress config for UEFI
  * Make changes to allow for different boot interception message
  configuration
  * Increase timeouts for some stages of deployment (mkfs ext3) to
  account for vexpress (lack of) speed.

.. _version_0_5_7:

Version 0.5.7
=============

* Allow a device's config to specify how to power cycle it.
* Pass --force-yes to apt-get & call lava-test reset after installing it.
* Increase wget connect timeout to see if we can work around a possible
  issue where the server gets busy, and doesn't connect quickly enough
  for getting the tarballs
* Stop reading the long-obsolete 'image_type' field from the job json.
* Add an field health_check in job schema to tell if the job is a health check
  job.

.. _version_0_5_6:

Version 0.5.6
=============

* by default, a shell command run on the board that fails will now
  fail the job.
* combine submit_results and submit_results_on_host into one action,
  although both action names are still supported.
* allow deployment from a compressed image file
* add support for optionally including a job id in the process name as
  seen by top

.. _version_0_5_5:

Version 0.5.5
=============
* allow the job file to contain unknown propertiies

.. _version_0_5_4:

Version 0.5.4
=============

* allow deployment from an image file as well as a rootfs/hwpack combination
* Auto accept the new snowball license update.

.. _version_0_5_3:

Version 0.5.3
=============

* Fix https://bugs.launchpad.net/lava-dispatcher/+bug/921527 - It is hard to
  follow the lava-dispatcher logging when debug why the test job failed

.. _version_0_5_2:

Version 0.5.2
=============

* Fix https://launchpad.net/bugs/921632 - still submit some results even if
  retrieve_results blows up
* Fix https://launchpad.net/bugs/925396 - lava-dispatcher exits when test
  failed
* Minor documentation updates

.. _version_0_5_1:

Version 0.5.1
=============

* Fix broken rc check (Paul Larson)

.. _version_0_5_0:

Version 0.5.0
=============

* Add new android_install_binaries action
* Fix problem when reporting failure messages that contain unicode
* Refactor click-through workaround, and add support for new omap3
  hwpacks
* fix lava-test installation detection

.. _version_0_4_5:

Version 0.4.5
=============
* extend lmc timeout to 24 hours
* retry until timeout for getting results
* pass on timeout in PrefixCommandRunner.run

.. _version_0_4_4:

Version 0.4.4
=============
* Fix an issue with linaro-media-create timing out prematurely

.. _version_0_4_3:

Version 0.4.3
=============
* Workaround for license acceptance in lmc on snowball
* Fix userdata deployment for origen and mx53
* Fix missing piece for errno 17 on deployment (bug #897918)

.. _version_0_4_2:

Version 0.4.2 (Milestone 2012.01)
=================================
* Job files can now specify the filesystem to use for the rootfs.
* It is now possible to include an auth token in the job file so that
  results can be submitted to a private bundle stream.
* Corrected errors with deploying Android 4.x
* Snowball improvements and workaround for reboot issues on snowball
* Better cleanup of temporary images if deployment fails
* Bug fixes: #905457, #906772.

.. _version_0_4_1:

Version 0.4.1 (Milestone 11.12)
===============================
* Add support for Origen
* Snowball default config fixes
* Add support for new snowball hwpacks
* Fix timeout usage in lava_test_install
* Added logging for sending and expecting statements.
* Bug fixes: #900990, #904544, #898525.

.. _version_0_4:

Version 0.4
===========
* Major refactoring of how commands are run on boards.
* Set PS1 in a way that works on ice cream sandwich builds
* Add --config-dir option.
* Consistently fail if deployment fails.
* Support for snowball V5 and later.

.. _version_0_3_5:

Version 0.3.5 (Milestone 11.11)
===============================
* Have soft_reboot look for a message that both android and regular images print
* Update android demo job to download urls that will hopefully exist for a while
* First pass at adding plugin support for lava actions
* Add a --validate switch for using the dispatcher to validate the schema
* Fix hang with add-apt-repository in oneiric
* Add LAVA support for Android on MX53 QS board
* Allow passing an option to the install step for lava-android-test
* Increase timeout for waiting on the network to come up
* Fix pypi installations issues
* Add l-m-c version to metadata
* Merge improvement for bug 874594 so the default timeout is shorten to 20mins
* Fix demo job to install and run the same test
* Remove old android tests and LavaAndroidClient
* Move all the stuff that knows about conmux to a concrete subclass of a new connection abstract class

.. _version_0_3_4:

Version 0.3.4 (Milestone 11.10)
===============================
* Documentation for lava-dispatcher is now available from lava-dispatcher.readthedocs.org
* Added support for snowball boards
* Move bootloader prompt string to device_type configuration file
* Bug fixes: #873043, #861115, #867858, #863091, #872948, #877045, #855384

.. _version_0_3:

Version 0.3 (Milestone 11.09)
=============================
* Local configuration data for lava-dispatcher is now stored in config files. (Please look at the README and examples of configuration)
* A new kernel package can be specified for testing directly in the lava-dispatcher
* The lava-dispatcher is now available as a package.
* Bug fixes: #836700, #796618, #831784, #833246, #844462, #856247, #813919, #833181, #844299, #844301, #844446, #845720, #850983, #827727, #853657.

.. _version_0_2:

Version 0.2 (Milestone 11.08)
=============================
* Transferring results from the test system to the dispatcher is now more reliable
* i.MX53 support added
* Support added for installing out-of-tree tests
* Bug fixes: #815986, #824622, #786005, #821385

Version 0.1 (Milestone 11.07)
=============================
* LAVA dispatcher now tries to make as much progress in the test run as possible despite failures of previous actions, and keeps track of which actions passed or failed rather than just whether the whole test run completed or not.
* Trial support for snowball board
* Bug fixes: #791725, #806571, #768453

