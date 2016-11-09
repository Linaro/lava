.. index:: qemu, extending qemu

.. _extending_qemu_options:

QEMU options
############

There are two ways to use QEMU in LAVA.

Virtualisation testing
**********************

If you want to test virtualisation on a :term:`DUT`, then you have complete
freedom to launch QEMU in any way you desire, including from a locally compiled
source tree with custom patches. It is often useful to separate the output of
the virtual machine from the host device or to run a test shell inside the
virtual machine as well as on the host device, so a :ref:`secondary_connection`
can be used. This is a relatively complex test job with particular issues about
how to identify the IP address of the virtual machine so that the secondary
connection can login over SSH.

.. seealso:: :ref:`using_secondary_connections` and
   :ref:`writing_secondary_connection_jobs`

The rest of this page deals with how to specify the options to QEMU when using
QEMU on the dispatcher for testing emulation within QEMU.

Emulation testing
*****************

LAVA also supports running QEMU on the dispatcher, allowing testing of an x86
virtual machine and emulation of other architectures using the same device. The
QEMU command line is built up by combining settings from the :term:`jinja2`
template, the :term:`device dictionary` and the :term:`job context`.

The Jinja2 template for QEMU tries to cover a range of use cases but QEMU has a
very long and complex set of possible options and commands.

The LAVA support for QEMU has three elements:

#. **substituted** - options into which values must be inserted by LAVA.

#. **mandatory** - options which LAVA needs to use to ensure the automation
   operates.

#. **specific** - options which are specific to particular test jobs.

Substitution support
********************

To execute QEMU in LAVA, various files need to be downloaded by LAVA, some may
need to be modified or decompressed by LAVA, but all of the final paths to the
files will be determined by LAVA. These paths need to be substituted into the
commands so that QEMU is able to locate the files.

This is handled in the test job definition using ``image_args`` with
placeholders like ``{{KERNEL}}``. The :ref:`first_job_definition` uses this
method.

.. seealso:: :ref:`first_deploy_action_qemu`

Mandatory support
*****************

Mandatory commands and options include ``-nographic`` so that LAVA is able to
interact with the virtual machine on the serial console instead of letting QEMU
launch a new window which would be problematic on dispatchers when X11 is not
available.

Mandatory commands also include admin constraints like limiting the amount of
memory available to each QEMU test job. This is achieved by allowing the ``-m``
option to take a variable in the :term:`device type` template but setting a
value for that variable in the :term:`device dictionary`. This value cannot
then be overridden by the test writer.

Other options of this kind include networking support, for example the MAC
address used by QEMU devices needs to be strictly controlled by admins so that
no two QEMU devices on one subnet have the same MAC address.

Specific support
****************

The breadth of the possible options available with QEMU means that there is a
lot of scope for customisation. Some of these elements have defaults in the
device type template which can be overridden by the test writer. Other options
can be specific to individual test jobs.

When writing a new test job, it is best to start with an example command line
based on how you would use QEMU to run the same test on your local machines.

Example command lines
*********************

An example QEMU command line might look like this:

.. code-block:: none

 /usr/bin/qemu-system-x86_64 -cpu host -enable-kvm -nographic \
  -net nic,model=virtio,macaddr=DE:AD:BE:EF:28:05 \
  -net tap -m 1024 -monitor none \
  -drive format=raw,file=/tmp/tmpUHeIM6/large-stable-6.img \
  -drive format=qcow2,file=/tmp/tmp2sbOlI/lava-guest.qcow2,media=disk

This example would break into:

* **Mandatory** from the device type template (using values from the device
  dictionary or the job context).

  * ``/usr/bin/qemu-system-x86_64``
  * ``-cpu host``
  * ``-enable-kvm``
  * ``-nographic``

* **Substituted** using ``image_args`` in the test job definition.

  * ``-drive format=raw,file=/tmp/tmpUHeIM6/large-stable-6.img``
  * ``-drive format=qcow2,file=/tmp/tmp2sbOlI/lava-guest.qcow2,media=disk``

A more complex QEMU command line would need to use ``extra_options`` in the
test job context. e.g.

.. code-block:: none

 /usr/bin/qemu-system-aarch64 -nographic -machine virt -cpu cortex-a57 -smp 1 \
  -m 2048 -global virtio-blk-device.scsi=off -device virtio-scsi-device,id=scsi \
  -kernel /tmp/tmpQi2ZR3/Image --append "console=ttyAMA0 root=/dev/vda rw" \
  -drive format=raw,file=/tmp/tmpQi2ZR3/ubuntu-core-14.04.1-core-arm64-ext4.img \
  -drive format=qcow2,file=/tmp/tmpMgsuvB/lava-guest.qcow2,media=disk

This example would break into:

* **Mandatory** from the device type template (using values from the device
  dictionary or the job context).

  * ``/usr/bin/qemu-system-aarch64``
  * ``-nographic``
  * ``-m 2048``

* **Substituted** using ``image_args`` in the test job definition.

  Use *substituted* for the complete argument. Include any other options
  which relate to the filepath into the ``image_args``.

  * ``-kernel /tmp/tmpQi2ZR3/Image --append "console=ttyAMA0 root=/dev/vda rw"``
  * ``-drive format=raw,file=/tmp/tmpQi2ZR3/ubuntu-core-14.04.1-core-arm64-ext4.img``
  * ``-drive format=qcow2,file=/tmp/tmpMgsuvB/lava-guest.qcow2,media=disk``

* **Specific** - using the :term:`job context` to override defaults:

  * ``-machine virt``
  * ``-cpu cortex-a57``

  To use ``/usr/bin/qemu-system-aarch64``, the job context also needs to
  include ``arch: arm64`` or ``arch: aarch64``:

* **Specific** - using ``extra_options`` in the job context:

  * ``-smp 1``
  * ``-global virtio-blk-device.scsi=off``
  * ``-device virtio-scsi-device,id=scsi``

.. _override_variables_context:

How to override variables
*************************

.. note:: The specifics of which variables, the names of the variables
   themselves and the possible values are determined by the device type
   template and this can be modified by the local admin. This guide can only
   cover the general principles and give examples using the default templates.

* Substitution support is handled by the test job pipeline once the relevant
  files have been downloaded. The test writer has the ability to add relevant
  options and flags to these commands using the ``image_args`` support in the
  test job definition.

  .. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
     :code: yaml
     :start-after: ACTION_BLOCK
     :end-before: # BOOT_BLOCK

* Mandatory options and commands cannot be overridden. These will either be
  hard-coded values in the device type template or variables set by the admin
  using the device dictionary.

* Specific options can be overridden in the job context. One of the most common
  specific options for QEMU in LAVA is ``arch``. This allows admins to
  configure QEMU devices in LAVA to support multiple architectures instead of
  needing at least one device for each supported architecture. The test writer
  specifies the architecture of the files provided in the test job definition
  and this then determines which QEMU binary is used to execute the files.

  .. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: metadata:

  When using the multiple architecture support, it is common to change the
  ``machine`` and ``cpu`` arguments passed to QEMU.

  .. include:: examples/test-jobs/qemu-aarch64.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: extra_options:

  (This example simply restates the defaults but any value which QEMU would
  accept as an argument to ``-machine`` and ``-cpu`` respectively could
  be used.)

  If using QEMU to emulate a microcontroller, you might need to use the ``vga``
  and ``serial`` options which each take a complete argument, passed unchanged
  to QEMU.

  Specific options can also extend beyond the range that the device type
  template needs to cover and in order to build a working QEMU command line,
  it is sometimes necessary to pass a list of further commands and options
  which LAVA needs to include into the final command line. This support is
  available using the ``extra_options`` job context variable:

  .. code-block:: yaml

   context:
     arch: arm64
     extra_options:
     - -global
     - virtio-blk-device.scsi=off
     - -smp
     - 1
     - -device
     - virtio-scsi-device,id=scsi

  .. note:: When specifying a QEMU command, ensure that the preceding hyphen is
     included as well as the hyphen indicating that the ``extra_options`` list
     is continuing. (``- -device``). When specifying an option to that command,
     ensure that there is only the hyphen for the list. (``- virtio...``).
     Errors in this syntax will cause the test job to fail as Incomplete when
     the QEMU command line is constructed.
