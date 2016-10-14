.. index:: lava-tool issues

.. _fixing_issues_with_lava_tool:

Fixing issues with lava-tool
############################

When using :ref:`lava-tool <lava_tool>` submit-job manually, this
error can be misleading::

 ERROR: Username provided but no token found.

``lava-tool`` is exact about the complete URL (not just the username),
so if you added authentication using ``http://`` then the lookup will
fail if you submit using ``https://``.

.. _scripted_job_submission:

Submitting jobs from a script
*****************************

When submitting a job using ``lava-tool submit-job``, the user is
requested to enter the password to open the keyring which stores the
lava :ref:`token <authentication_tokens>`. When submitting a job from
a script, the user can skip this step by adding the credentials in the
URL to the instance. ::

  $ lava-tool submit-job http://<login>:<token>@localhost/RPC2/

You can also use XML-RPC directly:

.. code-block:: python

  import xmlrpclib
  username = "USERNAME"
  token = "TOKEN_STRING"
  hostname = "HOSTNAME"
  server = xmlrpclib.ServerProxy("http://%s:%s@%s/RPC2" % (username, token, hostname))
  print server.system.listMethods()

gnomekeyring.IOError when submitting over ssh.
**********************************************

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

* Use a server version of Debian (or a remove the Gnome Keyring)
* Unset the DISPLAY environment variable in your shell (this will
  make the keyring library not use the GNOME keyring)
* Setup and use a file-based key ring::

    mkdir ~/.cache/keyring
    echo '
    [backend]
    default-keyring=keyring.backend.CryptedFileKeyring
    keyring-path=~/.cache/keyring/
    ' > ~/keyringrc.cfg

* Use a remote xmlrpclib call::

    import xmlrpclib
    import yaml

    config = yaml.dumps({ ... })
    server=xmlrpclib.ServerProxy("http://username:API-Key@localhost:8001/RPC2/")
    jobid=server.scheduler.submit_job(config)

Locked keyrings "locked collection"
***********************************

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
