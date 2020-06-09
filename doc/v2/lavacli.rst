.. index:: lavacli

.. _lavacli:

lavacli
#######

``lavacli`` is the preferred command-line tool for interacting with the
various services offered by LAVA via XML-RPC APIs as well as using ZMQ.
The full list of XML-RPC API calls is visible on the **Available
methods** link from the API menu::

 http://localhost/api/help

The API help page includes an example python script to connect to the local
instance. To add token support, use the syntax **username:token** for the
server concerned:

.. code-block:: python

 import xmlrpc.client

 server = xmlrpc.client.ServerProxy("https://%s:%s@%s/RPC2" % (username, token, server))

``lavacli`` is a native Python3 utility, the above example uses Python3
syntax.

See :ref:`xml_rpc` for more information.

lavacli allows you to interact with all LAVA objects:

* aliases
* device-types
* devices
* events
* jobs
* results
* tags
* workers

``lavacli`` supports multiple ``identities`` to interact with multiple
instances of LAVA and as multiple users.

``lavacli`` can be used by users directly or in scripts. Scripts used
by build servers and continuous integration tools should ideally use a
dedicated user account. ``lavacli`` does not use prompts or other
interactive operations and secrets like tokens can be provided using a
configuration file (``~/.config/lavacli.yaml``) if the command line
option is not suitable.

.. _installing_lavacli:

Installing lavacli
******************

``lavacli`` can be installed alongside LAVA if the top level ``lava``
package is installed on a :ref:`Debian-based distribution
<debian_installation>`. ``lavacli`` can also be installed on any remote
machine running a Debian-based distribution, without needing the rest
of LAVA. This allows a remote user to interact with any LAVA instance
on which the user has an account.::

  $ sudo apt update
  $ sudo apt install lavacli

(If you are installing on Debian Stretch, you will need to first enable
``backports`` to install ``lavacli``) and tell ``apt`` to use
``stretch-backports``::

 $ sudo apt -t stretch-backports install lavacli

.. _using_lavacli:

Using lavacli
*************

.. seealso:: :ref:`Creating & displaying a token <authentication_tokens>`

Once the token is created, add it to the configuration of lavacli.
Click on the "Display the token" link on the "Authentication Tokens"
page and copy the token. e.g. if your token was created on
validation.linaro.org then you may want to use the identity
``production``. The ``uri`` is typically provided on the *Available
methods* page, e.g. ``http://localhost/api/help``.

Run ``lavacli`` as your normal username. Avoid using ``sudo``.

The syntax is::

 --uri <URI>

.. code-block:: none

   $ lavacli identities add --token <TOKEN> --uri https://validation.linaro.org/RPC2 --username <USERNAME> production
   $ lavacli identities list
   Identities:
   * production

   $ lavacli -i production jobs submit ../refactoring/standard/qemu-amd64-standard-stretch.yaml
   1865811

