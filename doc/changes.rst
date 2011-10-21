Version History
***************

.. _version_0_3_4:

Version 0.3.4(Milestone 11.10)
==============================

* Documentation for lava-dispatcher is now available from lava-dispatcher.readthedocs.org

* Added support for snowball boards

* Move bootloader prompt string to device_type configuration file

* Bug fixes: #873043, #861115, #867858, #863091, #872948, #877045, #855384

.. _version_0_3:

Version 0.3(Milestone 11.09)
============================

* Local configuration data for lava-dispatcher is now stored in config files. (Please look at the README and examples of configuration)

* A new kernel package can be specified for testing directly in the lava-dispatcher

* The lava-dispatcher is now available as a package.

* Bug fixes: #836700, #796618, #831784, #833246, #844462, #856247, #813919, #833181, #844299, #844301, #844446, #845720, #850983, #827727, #853657.

.. _version_0_2:

Version 0.2(Milestone 11.08)
============================

* Transferring results from the test system to the dispatcher is now more reliable

* i.mx53 support added

* Support added for installing out-of-tree tests

* Bug fixes: #815986, #824622, #786005, #821385

Version 0.1(Milestone 11.07)
============================

* LAVA dispatcher now tries to make as much progress in the test run as possible despite failures of previous actions, and keeps track of which actions passed or failed rather than just whether the whole test run completed or not.

* Trial support for snowball board

* Bug fixes: #791725, #806571, #768453
