Running LAVA Scheduler
^^^^^^^^^^^^^^^^^^^^^^

LAVA Scheduler has two main components, the web application and the
daemon.  To process jobs, the scheduler daemon must be running.  Jobs
are accepted via the xmlrpc API on the web application.

Adding Devices
**************

Before jobs can be submitted or processed, devices must exist to run
them on.  To do this, login as an admin user in LAVA Server.

First, create a device type unless you are just adding a device for
which you have already created a type.  To create a device type from the
admin console, click the *Add* button next to *Device types* under the
*Lava_Scheduler_App* section.  You only need to provide the name.  Other
attributes of the device type such as default boot parameters will be
defined in the LAVA Dispatcher configuration files.

Once you have at least one device type, devices can be added from the
admin console as well.  To add a device, click the *Add* button next to
*Devices* under the *Lava_Scheduler_App* section.  Select the device
type and add the name of the device you wish to add.  The name given
here needs to correspond to the name of the device in the LAVA
Dispatcher config.

Running the Scheduler Daemon
****************************

If you installed from source or from pypi, you can start it manually
by simply running *lava-server manage lava-scheduler*, or by adding an
init script for it.
