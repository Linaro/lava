Using LAVA Scheduler
^^^^^^^^^^^^^^^^^^^^

Submitting Jobs
***************
Jobs can currently be submitted to the scheduler in one of two ways:
through the *lava-scheduler-tool* command line tool, or directly via
xmlrpc API.

Generating a Token
==================
Before a job can be submitted, a token must be generated. You can create a
token from the *API* menu at the top, then select *Authentication
Tokens*. From this page, click on *Create a new token*.  Once you have
created at least one token, you can click *Display this token* to show
it.  The token string can be copied from the browser for pasting into a
tool later, or saved to a file.

*NOTE*: Your user account may need the proper permission to allow it to
submit jobs. The user account will need two permissions::

  lava_scheduler_app | test job | Can add test job
  linaro_django_xmlrpc | auth token | Can add auth token

added to it via the Django admin panel.

Configuring lava-scheduler-tool
===============================
There are 3 ways to install the tool::

  # easiest
  sudo add-apt-repository ppa:linaro-maintainers/tools
  sudo apt-get update
  sudo apt-get install lava-scheduler-tool

  # from pypi
  pip install lava-scheduler-tool

  # from source for development with:
  bzr branch lp:lava-scheduler-tool
  cd lava-scheduler-tool ; ./setup.py develop

You'll probaly also want the lava-dashboard-tool installed as well. This can
be done using the same steps as outlined above.

To submit jobs using the scheduler, you should first set up the server
to which you will be submitting jobs::

 $ lava-tool auth-add https://user@example.com/RPC2/

In this example, *user@example.com* should be replaced with your userid
and webserver.  Using https is *highly* recommended since it will ensure
the token is passed to the server using ssl, but http will work if your
web server is not configured for ssl.

When entering this command, you will be prompted to enter the token.
Copy/paste the text of the token from your browser window here; it will
not be echoed to the screen.  Alternatively, you can also save the token
to a file and use the --token-file parameter to specify the file
containing your token.

Using lava-scheduler-tool
=========================

The first thing you may want to do is create a bundle stream in the LAVA
dashboard where you'll put your bundles. This is done with::

  lava-dashboard-tool make-stream --dashboard-url http://example.com/RPC2/ /anonymous/USERNAME/

Next you'll need a job file. You can read about an example job file `here`_

.. _here: http://lava.readthedocs.org/en/latest/qemu-deploy.html

You can now submit jobs by running ::

 $ lava scheduler submit-job http://user@example.com/RPC2/ jobfile.json

