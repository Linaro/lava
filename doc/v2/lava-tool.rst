.. index:: lava-tool

.. _lava_tool:

lava-tool
=========

``lava-tool`` is the command-line tool for interacting with the various
services offered by LAVA via XML-RPC APIs. The full list of API calls is
visible on the **Available methods** link from the API menu::

 http://localhost/api/help

``lava-tool`` is primarily designed to assist users and uses desktop
integration hooks provided by ``python-keyring`` and ``gnome-keyring``. If
writing or using scripts that need to interact with LAVA, it is recommended to
use XML-RPC API calls directly rather than calling lava-tool; this will avoid
the need to prompt for a password to access the local user keyring. Scripts
used by build servers and continuous integration tools should ideally use a
dedicated user account, for similar reasons.

The API help page includes an example python script to connect to the local
instance. To add token support, use the syntax **username:token** for the
server concerned::

 server = xmlrpclib.ServerProxy("https://%s:%s@%s/RPC2" % (username, token, server))

See :ref:`xml_rpc` for more information.

.. _installing_lava_tool:

Installing lava-tool
--------------------

``lava-tool`` is installed alongside LAVA by default, when the top level
``lava`` package is installed on a :ref:`Debian-based distribution
<debian_installation>`. ``lava-tool`` can also be installed on any remote
machine running a Debian-based distribution, without needing the rest of LAVA.
This allows a remote user to interact with any LAVA instance on which the user
has an account.::

  $ sudo apt update
  $ sudo apt install lava-tool

(If you are installing on Debian Jessie, you may want to first enable
``jessie-backports`` to install an updated ``lava-tool`` to use some superuser
operations or for other updates.)

.. important:: ``lava-tool`` is being updated and new features are being added
   as the migration to V2 continues. It is important that all users update
   the ``lava-tool`` package to continue working with V2.

.. _using_lava_tool:

Using lava-tool
---------------

Once the token is created, add it to the keyring for lava-tool. Click on the
"Display the token" link on the "Authentication Tokens" page and copy the
token. e.g. if your token was created on validation.linaro.org:

Older versions of ``lava-tool`` require a password on the keyring:

.. code-block:: none

  $ lava-tool auth-add https://<username>@validation.linaro.org/RPC2/
  Paste token for https://<username>@validation.linaro.org/RPC2/:
  Please set a password for your new keyring:
  Please confirm the password:
  Token added successfully for user <username>.

Current versions do not require a password:

.. code-block:: none

    neil@stretch:~$ lava-tool auth-add https://neil.williams@staging.validation.linaro.org/RPC2
    Paste token for https://neil.williams@staging.validation.linaro.org/RPC2/:
    Token added successfully for user neil.williams.


.. note:: Paste the token copied previously when it is asked above. Replace
   *username* with your username. If you don't already have a keyring, a new
   one will be created automatically. Set/use a password for keyring access as
   appropriate here.

.. see also:: :ref:`fixing_issues_with_lava_tool`

New features
------------

``lava-tool`` newer than ``0.19-1`` includes improved support for keyring
handling. The backend for token storage has changed and means that existing
authentications will not be usable to this new version. This change has been
made to fix persistent problems with the python-keyring support, including:

* DBus errors when used over SSH
* Interaction with gnome-keyring causing authentication failure
* Inability to list or remove authentications added to the keyring
* Inability to work with other keyring solutions.

The new backend is able to list and remove authentications. The new support
also removes the need for a default password on the user keyring, so lava-tool
will no longer pause waiting for password entry. A key benefit of the new
backend is the ability to shorten the authentication strings used for all
operations using ``lava-tool`` through the new ``auth-config`` support.

Once a token has been added, shortcuts can be enabled so that instead of
needing to type ``https://user.name@staging.validation.linaro.org/RPC2``,
the equivalent command can simply be ``staging`` by setting the ``endpoint``
shortcut to ``staging`` and setting the ``default-user``:

.. code-block:: none

    neil@stretch:~$ lava-tool auth-list
    No tokens found
    neil@stretch:~$ lava-tool auth-add https://neil.williams@staging.validation.linaro.org/RPC2
    Paste token for https://neil.williams@staging.validation.linaro.org/RPC2/:
    Token added successfully for user neil.williams.

Now set the user for this authentication as the default user for this endpoint
(staging.validation.linaro.org):

.. code-block:: none

    neil@stretch:~$ lava-tool auth-config --default-user https://neil.williams@staging.validation.linaro.org/RPC2
    Auth configuration successfully updated on endpoint https://staging.validation.linaro.org/RPC2.

Now set a shortcut for ``https://staging.validation.linaro.org/RPC2`` as
``staging``:

.. code-block:: none

    neil@stretch:~$ lava-tool auth-config --endpoint-shortcut staging https://neil.williams@staging.validation.linaro.org/RPC2
    Auth configuration successfully updated on endpoint https://staging.validation.linaro.org/RPC2.

Show the current authentication configuration:

.. code-block:: none

    neil@stretch:~$ lava-tool auth-list
    Endpoint URL: https://staging.validation.linaro.org/RPC2/
    endpoint-shortcut: staging
    default-user: neil.williams
    Tokens found for users: neil.williams
    ------------

Use the shortcut to submit a testjob:

.. code-block:: none

    neil@stretch:~$ cp /usr/share/doc/lava-server-doc/html/v2/examples/test-jobs/qemu-pipeline-first-job.yaml .
    neil@stretch:~$ lava-tool submit-job staging qemu-pipeline-first-job.yaml
    submitted as job: https://staging.validation.linaro.org/scheduler/job/169069

No more typos or forgetting the ``RPC2`` suffix, ``lava-tool`` does the work.
