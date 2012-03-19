Version History
***************

* Change snowball boot arg vmalloc=300M

* Convert the dispatcher to LAVA commnand. It can now be called from the shell
  by running ``lava dispatcher``. The old command line interface
  ``lava-dispatch`` is now deprecated and will be removed in the 0.8 release in
  three months. 

.. _version_0_5_9:

Version 0.5.9 (UNRELEASED)
==========================

.. _version_0_5_8:

Version 0.5.8 (UNRELEASED)
==========================


.. _version_0_5_7:

Version 0.5.7
=============

* Allow a device's config to specify how to power cycle it.
* Pass --force-yes to apt-get & call lava-test reset after installing it.
* Increase wget connect timeout to see if we can work around a possible
  issue where the server gets busy, and doesn't connect quickly enough
  for getting the tarballs
* Make the validation of the job file that happens before a job starts
  more rigorous.

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
