.. _publishing_artifacts:

Publishing artifacts
********************

Test writers might want to publish files from the device under test
(:term:`DUT`) to the outside world.

LAVA does not provide a specific command to publish files. However, LAVA does
provide a way to share secrets between the test writer and the device.

The secrets should be listed in the *job definition* as a dictionary called ``secrets``:

.. code-block:: yaml

  secrets:
    API_USER: kernel-ci
    API_KEY: b43614a9583f9c74b989914a91d1cfd9

This dictionary will be written to the lava overlay along with the test
definitions and scripts. The resulting file, called ``secrets``, can be sourced
from a shell script:

.. code-block:: shell

  API_USER=kernel-ci
  API_KEY=b43614a9583f9c74b989914a91d1cfd9


.. note:: In order to include a **secrets** dictionary, a job definition
          shouldn't be public. Hence a **visibility** set to *personal* or
          *group* (see :ref:`explain_first_job`).

Thanks to these secrets, the test writer can push files to an external server
that he does control.


Linaro LAVA-lab
===============

The Linaro lab team provides and maintains a default web server that test
writers can use to publish artifacts.

In order to use this server, you should ask admins for:
* an account on the server (and a token)
* a directory where to upload your files

This token should be provided to the device, thanks to the **secrets**
dictionary.

To publish an artifact, just make a POST request to your directory
inside a custom script so that the secret is not visible in the output of
``curl`` itself.

.. code-block:: shell

    curl -F 'path=@file_to_publish.ext' -F 'token=1234567890' https://files.linaro.org/artifacts/my/directory/

.. note:: It remains the responsibility of the user to keep the secret hidden
   - tokens can be revoked if misused.

The server will return the full url to the file you just published. You can
also list all files stored in the server by browsing
https://files.linaro.org/artifacts/

.. note:: Keep in mind that each file will be automatically deleted after some
          days and that quotas applies to each directories. For the Cambridge
          LAVA lab, the current timeout is 30 days.

Other third party sites can also be used. Access to such sites and obtaining the
tokens or secrets required for such sites is beyond the scope of this guide.