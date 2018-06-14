.. index:: gold standard

.. _providing_gold_standard_files:

Providing gold standard images
******************************

Test writers are strongly recommended to only use a known working setup
for their job. A set of gold standard jobs has been defined in
association with the Linaro QA team. These jobs will provide a known
baseline for test definition writers, in a similar manner as the
existing QA test definitions provide a base for more elaborate testing.

.. seealso:: :ref:`using_gold_standard_files`

There will be a series of images provided for as many device types as
practical, covering the basic deployments. Test definitions will be
required to be run against these images before the LAVA team will spend
time investigating bugs arising from tests. These images will provide a
measure of reassurance around the following issues:

* Kernel fails to load NFS or ramdisk.
* Kernel panics when asked to use secondary media.
* Image containing a different kernel to the gold standard fails
  to deploy.

The refactoring will provide :ref:`diagnostic_actions` which point at
these issues and recommend that the test is retried using the standard
kernel, dtb, initramfs, rootfs and other components.

The reason to give developers enough rope is precisely so that kernel
developers are able to fix issues in the test images before problems
show up in the gold standard images. Test writers need to work with the
QA team, using the gold standard images.

.. _creating_gold_standard_files:

Creating a gold standard image
==============================

Part of the benefit of a standard image is that the methods for
building the image - and therefore the methods for updating it,
modifying it and preparing custom images based upon it - must be
documented clearly.

Where possible, standard tools familiar to developers of the OS
concerned should be used, e.g. ``debootstrap`` for Debian based images.
The image can also be a standard OS installation. Gold standard images
are not "Linaro" images and should not require Linaro tools. Use
AutoLogin support where required instead of modifying existing images
to add Linaro-specific tools.

All gold standard images need to be kept up to date with the base OS as
many tests will want to install extra software on top and it will waste
time during the test if a lot of other packages need to be updated at
the same time. An update of a gold standard image still needs to be
tested for equivalent or improved performance compared to the current
image before replacing it.

The documentation for building and updating the image needs to be
provided alongside the image itself as a README. This text file should
also be reproduced on a wiki page and contain a link to that page. Any
wiki can be used - if a suitable page does not already exist elsewhere,
use wiki.linaro.org.

Other gold standard components
==============================

The standard does not have to be a complete OS image - a kernel with a
DTB (and possibly an initrd) can also count as a standard ramdisk
image. Similarly, a combination of kernel and rootfs can count as a
standard NFS configuration.

The same requirement exists for documenting how to build, modify and
update all components of the "image" and the set of components need to
be tested as a whole to represent a test using the standard.

In addition, information about the prompts within the image needs to be
exposed. LAVA no longer has a list of potential prompts and each job
must specify a list of prompts to use for the job.

Other information should also be provided, for example, memory
requirements or CPU core requirements for images to be used with QEMU
or dependencies on other components (like firmware or kernel support).

Test writers need to have enough information to submit a job without
needing to resubmit after identifying and providing missing data.

One or more sample test jobs is one way of providing this information
but it is still recommended to provide the prompts and other
information explicitly.

.. seealso:: :ref:`Using Gold standard files
   <using_gold_standard_files>`
