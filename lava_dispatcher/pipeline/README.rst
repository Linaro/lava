Requirements
============

See the whitepaper for detailed and updated information:
https://docs.google.com/a/linaro.org/document/d/17wjThA69fteT85q0D_cmzyGqQjaaH6OCKtN3qXGkvWw/edit#heading=h.9eocfm1tarco

See also the full documentation in lava-server:
http://localhost/static/docs/dispatcher-design.html
http://localhost/static/docs/dispatcher-format.html

Note that lava_dispatcher/pipeline/test/sample_jobs/basics.yaml is not intended
as a workable test job but as an outline of all possible layouts.

Functional:

- It should be possible to have multiple simultaneous connections to the
  device and run parallel tests on it. Example: one serial connection
  and one SSH connection.

- It should be possible to interact not only with "high-level" software
  such as bootloader and OS, but with bare metal as well.

- Support for different types of images:

  - pre-built and vendor-supplied images
  - existing media
  - kernel + ramdisk/rootfs
  - tftp
  - nfsroot

- Support for different bootloaders on same platform. Example: uboot,
  uefi, and second stage (grub) pipeline

- It should be possible to choose which device to boot from. This
  impacts both the deployment code and the boot code

- It must be possible to test advanced multi boot test cases with
  repetition - suspend, kexec, wake test cases. In special it is
  necessary to test wake, suspend, reboot, kexec etc.

- The dispatcher should be able to provide interactive support to
  low-level serial.  For some new devices, remote bringup is often
  necessary because developers can't have a device on their desks. When
  necessary, interact with the scheduler to put board online/offline.

Non-functional:

- Speed. Avoid as much overhead as possible.

- Security. Should not require to be run as root. If necessary, let's
  have a separate helper program that can be setuid to do the stuff that
  actually needs root privileges.

- Simplicity.

  - Having master image and test system on the same device makes several
    actions harder than they need to be. Master images must be booted
    from the network so that the actualy storage on the devices are left
    entirely to the test system. When possibel, deployment to the test
    system should be done by "just" dd'ing an image to the desired
    device.

  - Avoid as much as possible running commands on the target. When
    it is possible to perform some operation in the dispatcher host,
    let's not perform it on the target.

Design
======

The proposed design is based around the Pipes and Filters architectural
pattern, which is reified for instance in the UNIX pipes system. The
idea is to have every piece of funcionality as self-contained as
possible, and to be able to compose them in sequence to achieve the
desired high-level funcionality.

Main concepts in the design
---------------------------

- *Device* represents the device under test.

- *Connection* is a data connection between the dispatcher host and the
  device under test. Examples of connections: serial connection, SSH
  connection, adb shell, etc.

- *Action* an action that has to be performed. A Action can be a
  shell commands run on the target, an operations run on
  the dispatcher host, or anything. Actions should be as constrained as
  possible so that all possible errors can be easily tracked. Where
  multiple operations are required, use an action which contains
  an internal pipeline and add the individual commands as actions
  within that pipeline.

  Actions must be aggregated into a *Pipeline* - the top level object is
  always a pipeline. Pipelines can repeat actions and actions can include
  internal pipelines containing more actions. Actions have parameters which
  are set during the parsing of the YAML submission. Parameter data is
  static within each action and is used to validate the action before any
  pipeline is run. Dynamic data is set in the context which is available
  via the parent pipeline of any action. Actions must be idempotent and
  must raise a RuntimeError exception if the dynamic data is absent or
  unusable. Errors in parameter data must raise a JobError exception.
  Each command will receive a connection as an input parameter and can
  optionally provide a different connection to the command that
  comes after it. Usually, the first command in a pipeline will receive
  *None* as connection, and must provide a connection to the subsequent
  command.

  See `Connection Management`_ below for other requirements that
  Actions must observe.

- *Image* represents the test system that needs to be deployed to the
  target.

  Each command in a pipeline will be given a chance to insert data into
  the root filesystem of the image, before the pipeline starts to run.

- *Deployment* is a strategy to deploy a given image to a given device.
  Subclasses of deployment represent the different ways of deploying
  images to device, which depend on both the type of image and on the
  capabilities of the device.

- *Job*. A Job aggregates a *Device* representing the target device to
  be used, an *Image* to be deployed, and *Action* to be executed. The
  Action can be, and usually *will* be, a composite command composed
  of several subcommands.

  The chosen deployment strategy will be chosen based on the image and
  the device.

Connection management
---------------------

Connections to devices under test are often unreliable and have been a
major source of problems in automation. This way, in the case where a
connection failure (disconnection, serial corruption) during the
execution of a command, that command will be re-tried. Because of this,
every step performed by a command must be prepared to be idempotent,
i.e. to do nothing in the case where it has been performed before, and
more importantly, to not crash if has been performed before.

Exceptions
----------

LAVA must be clear on what was the likely cause of an incomplete test
job or a failed test result. Any one failure must trigger only one
exception. e.g. A JobError which results in a RuntimeError is still
a bug in the dispatcher code as it should have been caught during
the validation step.

- *JobError*: An Error arising from the information supplied as part of
    the TestJob. e.g. HTTP404 on a file to be downloaded as part of the
    preparation of the TestJob or a download which results in a file
    which tar or gzip does not recognise. This exception is used when
    data supplied as the parameters to an Action causes that action
    to fail. Job errors should always be supported by a unit test.

- *InfrastructureError: Exceptions based on an error raised by a component
    of the test which is neither the LAVA dispatcher code nor the
    code being executed on the device under test. This includes
    errors arising from the device (like the arndale SD controller
    issue) and errors arising from the hardware to which the device
    is connected (serial console connection, ethernet switches or
    internet connection beyond the control of the device under test).
    Actions are required to include code to check for likely
    infrastructure errors so that pipelines can retry or fail the
    test, recording whether a retry fixed the infrastructure error.

- *TestError*: exceptions raised when the device under test did not
    behave as expected.

- *RuntimeError*: Exceptions arising from dynamic data prepared by
    LAVA Dispatcher and failures of Actions not already handled by
    the code. Runtime errors are bugs in lava-dispatcher code. (It is
    also a bug to use the wrong exception type). Fixes for runtime
    error bugs should always include a unit test.

Gotchas
-------

The Pipeline design does use LavaContext, however, the context is intended
for *dynamic* data intended to be passed between actions. This data is
ephemeral, typically including the location of the scratch directory
and other data which although it may always exist in all jobs using
the same submission, will have different data within each submission.

It is entirely possible that the rest of LavaContext will go away or
that the context variable within the Pipeline design could be replaced
by an empty dict at the start of each job. Where the code currently pulls
data out of the LavaContext, this data may need to come from the job
parameters or be generated within the pipeline.

When storing dynamic data into the context, use the pipeline-specific
context.pipeline_data dict. Use the action.name or similar as the key
of the dict and create sub-trees within, where appropriate. The key
must be predictable by any subsequent action which may be interested.

Actions still need to be able to simulate the run behaviour without
reference to any context during the validation stage so that subsequent
actions can validate their own operations by checking for the existence
of data from previous actions. This validation happens in the submission
checks, so be sure to only check data, not run actions.

How specific should an Action be?
---------------------------------

As specific as possible. e.g. there were numerous bugs with the calculation
of offsets of images when preparing loop back mounts as well as in the
determination of why the subsequent mount operation may fail. Whenever one
action can or could cause different errors from within the same run function,
a separate action should be considered. Whenever an Action could be called from
multiple places but is too tied to one particular deployment, that action should
be split to move the generic code to an action which can be re-used and the
specific code to those particular deployments which need it. e.g. the MountAction
should not need to know about losetup, that would be the job of a LoopMountAction
which would set dynamic data about the required offset. The UnmountAction,
however, does not need to know about offsets of even whether the mount was using
a loopback device. Yet the error handler for the UnmountAction might need to
know about it being a LoopMountAction, in case it needs to track whether the
loopback device has been correctly freed.

Think of it like a shell script - using set -e wraps each line in a check,
so each line would be a separate action except where that line is just to store
data in a variable (the context.pipeline_data).

The simulation output of the pipeline should be similar to the output of a shell
script run under set -x.

If an Action can operate using different methods (e.g. downloader with http
or file or scp), then those decisions need to be made during the creation
of the pipeline, using dedicated actions. If appropriate these can inherit
from the general DownloadAction and call the base class to do the actual
download, restricting the method based actions to populating the dynamic
data during the verification step.
