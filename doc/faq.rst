What do you want from LAVA - FAQs
=================================

Jobs
----

Jobs not submitting
^^^^^^^^^^^^^^^^^^^

When using lava-tool submit-job manually, this error can be
misleading:

ERROR: Username provided but no token found.

Check the URL in use - http://user@localhost/RPC2 will fail,
http://user@localhost/RPC2/ should work. Note the trailing slash.

The error arises because the supplied URL does not precisely match the
authenticated URL used for the token (which would include the final
slash). The same can happen if the authentication uses https:// and
the request to submit uses http:// or vice versa.

To avoid such problems, consider exporting a variable in your
*~/.bashrc* to avoid typos.

Jobs submitted but not running
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There have been problems where a recently restarted vagrant session
accepts job submissions but fails to start jobs even though the
relevant device is idle. If lava is running with *--logging-level*
debug, the *lava-scheduler.log* should be  updated when devices check
for jobs. Admin access to the lava service will be required unblock
the scheduler by forcing the device status from Running to Idle in the
database.

If a device becomes stuck in cancel (device shows as canceling and the
job is not marked as finished), new jobs will be blocked for that
device. Use the lava-server management shell to force the device to
idle in the database. ::

  $ . /srv/lava/instances/development/bin/activate
  $ lava-server manage shell
  >>> from lava_scheduler_app.models import Device
  print Device.objects.get(hostname="qemu01").status

  status == 1 IDLE status == 2 RUNNING

It is possible to set a :term:`device status transition` but this might not
clear the state of the actual device:::

  >>> from lava_scheduler_app.models import DevicesStateTransition
  >>> DeviceStateTransition.objects.create(created_by=None, 
  device=Device.objects.get(hostname="qemu01"),
  old_state = 2,
  new_state = 1,
  message="forced",
  job=Device.objects.get(hostname="qemu01").current_job).save()

This correctly shows up in the list of device transitions.

One method to clear the status is to call the schedulermonitor
directly:

file.json below is the original JSON file submitted.::

  $ lava-server manage schedulermonitor lava-dispatch qemu01 file.json

This prompts an error report but also clears the invalid status.
gnomekeyring.IOError

I'm trying to submit a job over ssh, but I get a gnomekeyring.IOError. Why does this happen?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

  $ lava-tool auth-add http://administrator@192.168.11.100/RPC2/
  Paste token for http://administrator@192.168.11.100/RPC2/: 
  Traceback (most recent call last):
  ...
    File "/usr/lib/python2.7/dist-packages/keyring/backend.py", line
    163, in set_password
      password, True)
  gnomekeyring.IOError

This error occurs because the python functions that LAVA uses will
store the connection credentials in the Gnome keyring, if it is
available (default with current Gnome desktops). When you connect over
SSH, you will be unable to unlock the keyring, and you will see this
error. There are several methods available that can be used to provide
remote access.

Use a server version of Ubuntu (or a remove the Gnome Keyring)
unset the DISPLAY environment variable in your shell (this will
make the keyring library not use the GNOME keyring)
Setup and use a file-based key ring::

  mkdir ~/.cache/keyring
  echo '
  [backend]
  default-keyring=keyring.backend.CryptedFileKeyring
  keyring-path=~/.cache/keyring/
  ' > ~/keyringrc.cfg

Use a remote xmlrpclib call::

  import xmlrpclib
  import json

  config = json.dumps({ ... })
  server=xmlrpclib.ServerProxy("http://username:API-Key@localhost:8001/RPC2/")
  jobid=server.scheduler.submit_job(config)

Locked keyrings "locked collection"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

lava-tool auth-add can fail with a message::

  cannot create an item in a locked collection.

This results from a locked Gnome keyring and this can be unlocked in
the python console:

Your keyring password will need to be entered into the python console
to unlock and you will need to be outside of the lava instance (or
call /usr/bin/python) to do it::

  $ python
  >>> import gnomekeyring
  >>> gnomekeyring.unlock_sync(None, 'mypassword');

if that fails, see gnomekeyring.IOError above.

DBus unknown method OpenSession
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This exception can occur with some versions of gnome-keyring::

  File "/usr/lib/python2.7/dist-packages/dbus/connection.py", line
  651, in call_blocking message, timeout)
  dbus.exceptions.DBusException:
  org.freedesktop.DBus.Error.UnknownMethod: Method "OpenSession" with
  signature "ss" on interface "org.freedesktop.Secret.Service" doesn't
  exist

This appears to be Issue #65 in python-keyring which describes it as::

    The bug was introduced in gnome-keyring 3.4 and fixed in this
    commit:
    http://git.gnome.org/browse/gnome-keyring/commit/?id=5dccbe88eb94eea9934e2b7c83e818bd21be4fd2

It looks like it should be fixed in gnome-keyring 3.5, but haven't
verified this.

gnome-keyring 3.8 is available in Debian experimental but did not fix
this issue when tested.

An alternative is to disable the specific part of gnome-keyring which
causes this bug::

  /etc/xdg/autostart/gnome-keyring-secrets.desktop 

Either remove this file or change the autostart values to::

  X-GNOME-AutoRestart=false
  X-GNOME-Autostart-Notify=false

Installation problems/failures with lava-deployment-tool and
postgresql (on Ubuntu 12.04.2)

Ran::

  $ ./lava-deployment-tool setup
  $ ./lava-deployment-tool install testinstance

and noticed the following error::

  psql: could not connect to server: No such file or directory
  Is the server running locally and accepting connections on Unix domain
  socket /var/run/postgresql/.s.PGSQL.5432"?
  createuser: could not connect to database postgres: could not connect
  to server: No such file or directory

If you look in /var/log/postgresql/postgresql-9.1-main.log you may
find an entry that looks like::

  BST FATAL:  could not create shared memory segment: Invalid argument
  BST DETAIL:  Failed system call was shmget(key=5432001, size=41263104,
  03600).
  BST HINT:  This error usually means that PostgreSQL's request for a
  shared memory segment exceeded your kernel's SHMMAX parameter.  You
  can either reduce the request size or reconfigure the kernel with
  larger SHMMAX.  To reduce the request size (currently 41263104 bytes),
  reduce PostgreSQL's shared memory usage, perhaps by reducing
  shared_buffers or max_connections.

The PostgreSQL documentation contains more information about shared
memory configuration.

Changed the entry for shared_buffers in
/etc/postgresql/9.1/main/postgresql.conf from 32MB to 8MB and 
restarted the service ::

  $ sudo service postgresql restart 
   * Restarting PostgreSQL 9.1 database server  [ OK ] 
  $ sudo service postgresql status
  Running clusters: 9.1/main

The alternative, as suggested, is to increase the size of
kernel.shmmax value (e.g., 8589934592) in /etc/sysctl.conf and reload
::

  $ sudo sysctl -p

If you were now to reinstall the testinstance you should no longer see
the error about not being able to connect to the database when the
instance is created. ::

  $ ./lava-deployment-tool remove testinstance
  $ ./lava-deployment-tool install testinstance

With these changes in place the Lava instance is available on
reboot. It would previously fail because the postgres service had
failed to load (i.e., could not create shared memory segment: Invalid
argument).

Vagrant
-------

Vagrant and virtualbox
^^^^^^^^^^^^^^^^^^^^^^

Vagrant may initially set up with insufficient RAM assigned. Start
virtualbox and increase the RAM assigned to the vagrant VM before
starting vagrant, if you want to use qemu to run LAVA tests. Vagrant
prefers particular versions of virtualbox. Vagrant version 1.0.3 does
not work with virtualbox 4.2 but a vagrant session setup in an earlier
version of virtualbox can still be accessed from the virtualbox
manager. Login as vagrant:vagrant. 

Others
------

Why do health checks run even when "Skip Health Check" is selected when bringing a device online?
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Health checks will run in the following circumstances when "Skip
Health check" has been selected:

 * When the health status of the device is in Unknown, Fail or Looping
 * When the device has been offline for long enough that a health
   check is already overdue.
