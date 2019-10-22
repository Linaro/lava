.. index:: qemu, extending qemu, QEMU - options

.. _extending_qemu_options:

QEMU options
############

There are two ways to use QEMU in LAVA.

Virtualization testing
**********************

If you want to test virtualization on a :term:`DUT`, then you have
complete freedom to launch QEMU in any way you desire, including from a
locally compiled source tree with custom patches. It is often useful to
separate the output of the virtual machine from the host device or to
run a test shell inside the virtual machine as well as on the host
device, so a :ref:`secondary_connection` can be used. This is a
relatively complex test job with particular issues about how to
identify the IP address of the virtual machine so that the secondary
connection can login over SSH.

.. seealso:: :ref:`using_secondary_connections` and
   :ref:`writing_secondary_connection_jobs`

The rest of this page deals with how to specify the options to QEMU
when using QEMU on the dispatcher for testing emulation within QEMU.

Emulation testing
*****************

LAVA also supports running QEMU on the dispatcher, allowing testing of
QEMU running on the host architecture of the worker. In many, but not
all, cases this will create an x86 virtual machine. Emulation of other
architectures is possible using the same device. The QEMU command line
is built up by combining settings from the :term:`jinja2` template, the
:term:`device dictionary` and the :term:`job context`.

The Jinja2 template for QEMU tries to cover a range of use cases but
QEMU has a very long and complex set of possible options and commands.

The LAVA support for QEMU has three elements:

#. **substituted** - options into which values must be inserted by
   LAVA.

#. **mandatory** - options which LAVA needs to use to ensure the
   automation operates.

#. **specific** - options which are specific to particular test jobs.

Substitution support
********************

To execute QEMU in LAVA, various files need to be downloaded by LAVA,
some may need to be modified or decompressed by LAVA, but all of the
final paths to the files will be determined by LAVA. These paths need
to be substituted into the commands so that QEMU is able to locate the
files.

This is handled in the test job definition using ``image_arg`` with
placeholders like ``{{KERNEL}}``. The :ref:`first_job_definition` uses
this method.

.. seealso:: :ref:`first_deploy_action_qemu`

Mandatory support
*****************

Mandatory commands and options include ``-nographic`` so that LAVA is
able to interact with the virtual machine on the serial console instead
of letting QEMU launch a new window which would be problematic on
dispatchers when X11 is not available.

Mandatory commands also include admin constraints like limiting the
amount of memory available to each QEMU test job. This is achieved by
allowing the ``-m`` option to take a variable in the :term:`device
type` template but setting a value for that variable in the
:term:`device dictionary`. This value cannot then be overridden by the
test writer.

Other options of this kind include networking support, for example the
MAC address used by QEMU devices needs to be strictly controlled by
admins so that no two QEMU devices on one subnet have the same MAC
address.

The ``arch`` option in the :term:`job context` is used in the
:term:`jinja2` template to determine which QEMU binary to execute.

.. seealso:: :ref:`qemu_host_arch`

Specific support
****************

The breadth of the possible options available with QEMU means that
there is a lot of scope for customization. Some of these elements have
defaults in the device type template which can be overridden by the
test writer. Other options can be specific to individual test jobs.

When writing a new test job, it is best to start with an example
command line based on how you would use QEMU to run the same test on
your local machines.

Example command lines
*********************

An example QEMU command line might look like this:

.. code-block:: none

 /usr/bin/qemu-system-x86_64 -cpu host -enable-kvm -nographic \
  -net nic,model=virtio,macaddr=DE:AD:BE:EF:28:05 \
  -net tap -m 1024 -monitor none \
  -drive format=raw,file=/tmp/tmpUHeIM6/large-stable-6.img \
  -drive format=qcow2,file=/tmp/tmp2sbOlI/lava-guest.qcow2,media=disk

This example, on an x86_64 worker, would break into:

* **Mandatory** from the device type template (using values from the
  device dictionary or the job context).

  * ``/usr/bin/qemu-system-x86_64``
  * ``-cpu host``
  * ``-enable-kvm``
  * ``-nographic``

* **Substituted** using ``image_arg`` in the test job definition.

  * ``-drive format=raw,file=/tmp/tmpUHeIM6/large-stable-6.img``
  * ``-drive format=qcow2,file=/tmp/tmp2sbOlI/lava-guest.qcow2,media=disk``

A more complex QEMU command line would need to use ``extra_options`` in
the test job context. e.g.

.. code-block:: none

 /usr/bin/qemu-system-aarch64 -nographic -machine virt -cpu cortex-a57 -smp 1 \
  -m 2048 -global virtio-blk-device.scsi=off -device virtio-scsi-device,id=scsi \
  -kernel /tmp/tmpQi2ZR3/Image --append "console=ttyAMA0 root=/dev/vda rw" \
  -drive format=raw,file=/tmp/tmpQi2ZR3/ubuntu-core-14.04.1-core-arm64-ext4.img \
  -drive format=qcow2,file=/tmp/tmpMgsuvB/lava-guest.qcow2,media=disk

.. note:: The use of the ``cpu`` option in the job context **disables**
   the use of ``-enable-kvm``. If the worker can support KVM
   acceleration, this can be enabled using more QEMU options.

   .. seealso:: :ref:`qemu_host_arch`

This example would break into:

* **Mandatory** from the device type template (using values from the
  device dictionary or the job context).

  * ``/usr/bin/qemu-system-aarch64``
  * ``-nographic``
  * ``-m 2048``

* **Substituted** using ``image_arg`` in the test job definition.

  Use *substituted* for the complete argument. Include any other
  options which relate to the filepath into the ``image_arg``.

  * ``-kernel /tmp/tmpQi2ZR3/Image --append "console=ttyAMA0 root=/dev/vda rw"``
  * ``-drive format=raw,file=/tmp/tmpQi2ZR3/ubuntu-core-14.04.1-core-arm64-ext4.img``
  * ``-drive format=qcow2,file=/tmp/tmpMgsuvB/lava-guest.qcow2,media=disk``

* **Specific** - using the :term:`job context` to override defaults:

  * ``-machine virt``
  * ``-cpu cortex-a57``

  To use ``/usr/bin/qemu-system-aarch64``, the job context also needs
  to include ``arch: arm64`` or ``arch: aarch64``:

* **Specific** - using ``extra_options`` in the job context:

  * ``-smp 1``
  * ``-global virtio-blk-device.scsi=off``
  * ``-device virtio-scsi-device,id=scsi``

.. _override_variables_context:

How to override variables
*************************

.. note:: The specifics of which variables, the names of the variables
   themselves and the possible values are determined by the device type
   template and this can be modified by the local admin. This guide can
   only cover the general principles and give examples using the
   default templates.

* Substitution support is handled by the test job pipeline once the
  relevant files have been downloaded. The test writer has the ability
  to add relevant options and flags to these commands using the
  ``image_arg`` support in the test job definition.

  .. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
     :code: yaml
     :start-after: ACTION_BLOCK
     :end-before: # BOOT_BLOCK

* Mandatory options and commands cannot be overridden. These will
  either be hard-coded values in the device type template or variables
  set by the admin using the device dictionary.

* Specific options can be overridden in the job context. One of the
  most common specific options for QEMU in LAVA is ``arch``. This
  allows admins to configure QEMU devices in LAVA to support multiple
  architectures instead of needing at least one device for each
  supported architecture. The test writer specifies the architecture of
  the files provided in the test job definition and this then
  determines which QEMU binary is used to execute the files.

  .. include:: examples/test-jobs/qemu-pipeline-first-job.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: metadata:

  When using the multiple architecture support, it is common to change
  the ``machine`` and ``cpu`` arguments passed to QEMU.

  .. include:: examples/test-jobs/qemu-aarch64.yaml
     :code: yaml
     :start-after: visibility: public
     :end-before: extra_options:

  (This example simply restates the defaults but any value which QEMU
  would accept as an argument to ``-machine`` and ``-cpu`` respectively
  could be used.)

  If using QEMU to emulate a microcontroller, you might need to use the
  ``vga`` and ``serial`` options which each take a complete argument,
  passed unchanged to QEMU.

  Specific options can also extend beyond the range that the device
  type template needs to cover and in order to build a working QEMU
  command line, it is sometimes necessary to pass a list of further
  commands and options which LAVA needs to include into the final
  command line. This support is available using the ``extra_options``
  job context variable:

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

  .. note:: When specifying a QEMU command, ensure that the preceding
     hyphen is included as well as the hyphen indicating that the
     ``extra_options`` list is continuing. (``- -device``). When
     specifying an option to that command, ensure that there is only
     the hyphen for the list. (``- virtio...``). Errors in this syntax
     will cause the test job to fail as Incomplete when the QEMU
     command line is constructed.

How to specify QEMU environment options
***************************************

* QEMU also evaluates environment options that are used at runtime to
  determine e.g. what subsystem should be used for the sound output on
  the host. For obvious security reasons there is **no way** to
  influence environment variables from within a job. But LAVA provides
  the capability to specify (globally at the server level) what
  environment variables are to be used for jobs in the file
  ``env.yaml``. See :ref:`simple_admin`.

* One example is the use of ``-soundhw hda`` which emulates a soundcard
  on the target. To avoid having any sound output on the host (or
  worker), you can specify QEMU_AUDIO_DRV like so in
  ``/etc/lava-server/env.yaml``:

  .. code-block:: yaml

    # A dictionary of (key, value) that will be added to the inherited environment.
    # If a key does not already exist in the inherited environment, it's added.
    # default: an empty dictionary
    overrides:
      LC_ALL: C.UTF-8
      LANG: C
    #  http_proxy: http://lava-lab-proxy
    #  https_proxy: http://lava-lab-proxy
    #  ftp_proxy: http://lava-lab-proxy
      PATH: /usr/local/bin:/usr/local/sbin:/bin:/usr/bin:/usr/sbin:/sbin
    #
    # For qemu-system-* (device_type qemu) if -soundhw is passed,
    # enable this to not forward sound to the host.
    # Check qemu-system-x86_64 --audio-help for other options.
      QEMU_AUDIO_DRV: none

.. index:: QEMU - host architecture, QEMU - workers

.. _qemu_host_arch:

Host architecture support
*************************

QEMU will run test jobs of any supported combination of architecture,
machine and CPU option. However, the underlying hardware of the worker
can dramatically improve performance of QEMU test jobs if the
appropriate acceleration can be used. This comes with a penalty that
test jobs using hardware acceleration for virtual machines of one
architecture will not transfer easily to another QEMU device (on this
or some other LAVA instance) where hardware acceleration is only
available for a different architecture. There will need to be changes
to the test job submission. Running without hardware acceleration
allows for portable test job submissions, however test jobs will not
only run more slowly but also with wider variation in speed. This may
make it hard to get sensible timeouts or usable results within a
reasonable timeframe.

The ``-enable-kvm`` support is used as a default, based on x86_64
workers. Specifying the ``-cpu`` option **disables** the
``-enable-kvm`` option in the LAVA Jinja2 templates but test writers
are able to add KVM acceleration using more QEMU options.

There are administrative issues here. It is entirely possible for a
worker to not be x86_64 architecture. It is also possible to have QEMU
devices on more than one worker and for those workers to be of
differing architectures. To handle this, admins will need to:

* Create a copy of the ``qemu.jinja2`` template and name it according
  to their own convention, for example ``qemu-arm.jinja2``.
* Set the ``extends`` of the QEMU devices on each worker to the
  corresponding QEMU jinja2 template.
* Create a new health check for the new Jinja2 template. For example,
  ``qemu-arm.jinja2`` needs a health check called ``qemu-arm.yaml`` in
  the health-checks directory of the master.
* Add device tags so that test writers can specify KVM acceleration
  where required. For example, ``kvm_arm`` on the devices extending
  ``qemu-arm.jinja2`` and ``kvm_x86_64`` on the devices extending the
  existing ``qemu.jinja2``.

The ``device_type`` of all the QEMU devices can remain the same.

The changes to the test job may not be intuitive - the QEMU support can
require some experimentation and reading, depending on the hardware.

For example, using the `SynQuacer
<https://www.socionext.com/en/products/assp/SC2A11/>`_ the options
required to be able to run 32bit ARM code using the KVM accelerator
require running the 64bit QEMU binary:

.. code-block:: yaml

    context:
      arch: arm64
      netdevice: user
      machine: virt-2.10,accel=kvm
      cpu: host,aarch64=off
      guestfs_interface: virtio
     tags:
      - kvm-arm

.. note:: Even if there are no x86_64 workers running QEMU, there
   will still need to be a suitable health check and it is recommended
   to have a copy of the Jinja2 template in case an x86_64 worker is
   added later.

LAVA test storage
*****************

If one or more test actions are included in a QEMU job, LAVA will
create a disk image and will attach it to QEMU using a command like:

.. code-block:: none

 -drive format=qcow2,file=<temporary_path>/lava-guest.qcow2,media=disk,if=<interface>,id=lavatest

The interface can be set in the device_type template or in the test job
context using the ``guestfs_interface`` key in the context. Supported
values include ``ide scsi virtio none`` with a default of ``ide``. The
size of the image is controlled via the ``guestfs_size`` parameter
(default 512M).

Some emulated devices have no bus available for attaching this image
(Ex: cubieboard). Some emulated devices have an available bus but qemu
is unable to attach to it due to the selected architecture (like
vexpress). For these boards, you need to set ``guestfs_interface`` to
``None`` and add a device with ``drive=lavatest``. The "lavatest" id
can be set via the ``guestfs_driveid`` job option. If no storage bus is
available, you will also need to attach a device which permit to attach
a storage bus.

Example for qemu cubieboard:
(Cubieboard have an AHCI bus, but the support is incomplete)

.. literalinclude:: examples/test-jobs/qemu-cubieboard.yaml
     :language: yaml
     :linenos:
     :lines: 49-57
     :emphasize-lines: 6

Example for qemu vexpress-a9:
(vexpress have a virtio bus, but by default, qemu try to add the drive as PCI virtio)

.. literalinclude:: examples/test-jobs/qemu-vexpress-a9.yaml
     :language: yaml
     :linenos:
     :lines: 49-57
     :emphasize-lines: 6

Example for Qemu PPC bamboo:

.. literalinclude:: examples/test-jobs/qemu-ppc-bamboo.yaml
     :language: yaml
     :linenos:
     :lines: 33-42
     :emphasize-lines: 6,7

