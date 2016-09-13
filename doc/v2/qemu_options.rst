.. index:: qemu, extending qemu

.. _extending_qemu_options:

Extending the options passed to QEMU
####################################

The Jinja2 template for QEMU tries to cover a range of use cases but QEMU has a
very long and complex set of possible options and commands.

The LAVA support has three elements:

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
  * ``-machine virt -cpu cortex-a57``
  * ``-m 2048``

* **Substituted** using ``image_args`` in the test job definition.

  * ``-kernel /tmp/tmpQi2ZR3/Image --append "console=ttyAMA0 root=/dev/vda rw"``
  * ``-drive format=raw,file=/tmp/tmpQi2ZR3/ubuntu-core-14.04.1-core-arm64-ext4.img``
  * ``-drive format=qcow2,file=/tmp/tmpMgsuvB/lava-guest.qcow2,media=disk``

* **Specific** - using ``extra_options`` in the job context:

  * ``-smp 1``
  * ``-global virtio-blk-device.scsi=off``
  * ``-device virtio-scsi-device,id=scsi``


* **Specific** - using ``extra_options`` in the job context:

  * ``-smp 1``
  * ``-global virtio-blk-device.scsi=off``
  * ``-device virtio-scsi-device,id=scsi``

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
     :end-before: BOOT_BLOCK

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
