# Adding a new device type

The integration process is different for every new device type. Therefore,
this documentation can only provide hints about such devices, based on
experience within the LAVA software and lab teams. **Please** talk to us
**before** starting on the integration of a new device type using the
mailing lists.

Integrating a new device type will involve some level of development
work. Testing new device type templates requires setting up a developer
workflow and running unit tests as well as running test jobs on a LAVA
instance. If the new device type involves a new boot or deployment
method, there will also need to be changes in the `lava-dispatcher`
codebase.

## Device requirements

It is not possible to automate every piece of hardware, there are a number
of critical limitations.

### Power

Devices **MUST** support automated resets either by the removal of all
power supplied to the DUT or a full reboot or other reset which clears
all previous state.

**Every** boot **must** reliably start, without interaction, directly
from the first application of power.

!!! warning "Power leaks"
    Some devices are capable of drawing power over the serial line used
    to control the device, despite the actual power supply being
    disconnected. Sometimes this requires a period of time to discharge
    capacitors on the board (fixable by adding a sleep in the power
    control commands). Sometimes this power leak can cause the device to
    latch into a particular bootloader mode or other state which prevents
    the automation from proceeding.

### Serial console

LAVA expects to automate devices by interacting with the serial port
immediately after power is applied to the device. The bootloader
**must** interact with the serial port. If a serial port is not
available on the device, suitable additional hardware **must** be
provided before integration can begin.

### Networking

**Ethernet** — all devices using Ethernet interfaces in LAVA **must**
have a unique MAC address on each interface. The MAC address **must** be
persistent across reboots.

### Reproducibility

Reproducibility is the ability to deploy exactly the same software to
the same board(s) and running exactly the same tests many times in a
row, getting exactly the same results each time.

For automation to work, all device functions which need to be used in
automation **must** always produce the same results on each device of a
specific device type, irrespective of any previous operations on that
device, given the same starting hardware configuration.

There is no way to automate a device which behaves unpredictably.

### Reliability

Reliability is the ability to run a wide range of test jobs, stressing
different parts of the overall deployment, with a variety of tests and
**always** getting a `Complete` test job. There must be no `JobError` or
`InfrastructureError` failures and there should be limited variability
in the time taken to run the test jobs.

### Scriptability

The device **must** support deployment of files and booting without
**any** need for a human to monitor or interact with the process. The
need to press buttons is undesirable but can be managed in some cases by
using relays.

### Scalability

All methods used to automate a device **must** have minimal footprint
in terms of load on the workers, complexity of scripting support and
infrastructure requirements.

This is a complex area and can trivially impact on both reliability and
reproducibility as well as making it much more difficult to debug problems
which do arise. Admins must also consider the complexity of combining
multiple different devices which each require multiple layers of support.

Some devices may need:

- Relays to work around buttons
- Specialized hardware to work around deployment limitations
- Complex scripting around power control
- A need to use Docker for automation

Any one of these burdens will make debugging issues on the worker and on
the devices difficult. Any combination of these burdens make debugging
many times more difficult than any one burden alone.

## Integration process

To add support for a new device type, a certain amount of development
and testing **will** be required.

For most device types, extending an existing base template should be
enough. For other device types, new dispatcher action classes and new or
modified strategy classes will be needed. This typically involves a lot
of development time — make sure that you contribute upstream so that your
local changes do not break when you next upgrade your LAVA instance(s).

### Find a similar existing device type

Check the already
[supported device types](https://gitlab.com/lava/lava/-/tree/master/etc/dispatcher-config/device-types)
for:

- Similar bootloader
- Similar deployment type
- Similar deployment or boot process
- Similar sequence of boot steps

If you do not find something similar, we strongly recommend that you
**stop** and [talk to us](../../introduction/contact.md) before doing
anything else.

### Extend from an existing device type template

All new device type templates need to `extend 'base.jinja2'`, but there
are other base templates which simplify the process for certain bootloaders.
See [base templates](../../technical-references/configuration/device-type-template.md#base-templates)
for the list.

Avoid directly extending any of the templates which do not have the
`base` prefix — instead copy the existing template for your new device
type.

### Extend the template unit tests

All device type template files in `tests/lava_scheduler_app/devices`
will be checked for simple YAML validity by the `test_all_templates`
unit test. However, a dedicated unit test is recommended for all but the
simplest of new device type templates. You can edit
`tests/lava_scheduler_app/test_templates.py` and add a new unit test
for your device-type based on one of the existing test functions.

Every time you make a change to the new template, re-run the template tests:

```shell
pytest tests/lava_scheduler_app/test_templates.py
```

## See also

- [Adding new actions](./new-actions.md)
- [Device type templates](../../technical-references/configuration/device-type-template.md)
- [Device dictionary](../../technical-references/configuration/device-dictionary.md)
