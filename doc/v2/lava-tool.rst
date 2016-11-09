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

.. _using_lava_tool:

Using lava-tool
---------------

Once the token is created, add it to the keyring for lava-tool. Click on the
"Display the token" link on the "Authentication Tokens" page and copy the
token. e.g. if your token was created on validation.linaro.org::

  $ lava-tool auth-add https://<username>@validation.linaro.org/RPC2/
  Paste token for https://<username>@validation.linaro.org/RPC2/:
  Please set a password for your new keyring:
  Please confirm the password:
  Token added successfully for user <username>.

.. note:: Paste the token copied previously when it is asked above. Replace
   *username* with your username. If you don't already have a keyring, a new
   one will be created automatically. Set/use a password for keyring access as
   appropriate here.

.. see also:: :ref:`fixing_issues_with_lava_tool`
