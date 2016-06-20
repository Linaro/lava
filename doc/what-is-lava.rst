What is LAVA?
*************

LAVA is the Linaro Automation and Validation Architecture.

LAVA is a continuous integration system for deploying operating
systems onto physical and virtual hardware for running tests.
Tests can be simple boot testing, bootloader testing and system
level testing, although extra hardware may be required for some
system tests. Results are tracked over time and data can be
exported for further analysis.

LAVA is a collection of participating components in an evolving
architecture. LAVA aims to make systematic, automatic and manual
quality control more approachable for projects of all sizes.

LAVA is designed for validation - testing whether the code that
engineers are producing "works", in whatever sense that
means. Depending on context, this could be many things, for example:

* testing whether changes in the Linux kernel compile and boot
* testing whether the code produced by gcc is smaller or faster
* testing whether a kernel scheduler change reduces power consumption
  for a certain workload
* etc.
 
LAVA is good for automated validation. LAVA tests the Linux kernel on
a range of supported boards every day. LAVA tests proposed android
changes in gerrit before they are landed, and does the same for other
projects like gcc. Linaro runs a central validation lab in Cambridge,
containing racks full of computers supplied by Linaro members and the
necessary infrastucture to control them (servers, serial console
servers, network switches etc.)

.. note:: This overview document explains LAVA using
          http://validation.linaro.org/ which is the official
          production instance of LAVA hosted by Linaro. Where examples
          reference ``validation.linaro.org``, replace with the fully
          qualified domain name of your LAVA instance.

What is LAVA **not**?
*********************

* LAVA is **not** a set of tests - it is infrastructure to enable
  users to run their own tests.

* LAVA is **not** a test lab - it is the software that can used in a
  test lab to control test devices.
