Using LAVA Scheduler
^^^^^^^^^^^^^^^^^^^^

Submitting Jobs
***************
Jobs can currently be submitted to the scheduler in one of two ways:
through the *lava-scheduler-tool* command line tool, or directly via
xmlrpc API.

Generating a Token
==================
Before a job can be submitted, a token must be generated.  Logged in as
a user with *lava_scheduler_app | test job | Can add test job* and
*linaro_django_xmlrpc | auth token | Can add auth token* permissions
enabled, select *API* from the menu at the top, then *Authentication
Tokens*. From this page, click on *Create a new token*.  Once you have
created at least one token, you can click *Display this token* to show
it.  The token string can be copied from the browser for pasting into a
tool later, or saved to a file.

Using lava-scheduler-tool
=========================
LAVA Scheduler Tool is actually a plugin to LAVA Tool.  It can be
installed from debian packages, source, or pypi in the same way
described for installing the scheduler in the installation section.

To submit jobs using the scheduler, you should first set up the server
to which you will be submitting jobs.
With lava-scheduler-tool installed, run ::

 $ lava-tool auth-add https://user@example.com/lava-server/RPC2/

In this example, *user@example.com* should be replaced with your userid
and webserver.  Using https is *highly* recommended since it will ensure
the token is passed to the server using ssl, but http will work if your
web server is not configured for ssl.

When entering this command, you will be prompted to enter the token.
Copy/paste the text of the token from your browser window here; it will
not be echoed to the screen.  Alternatively, you can also save the token
to a file and use the --token-file parameter to specify the file
containing your token.

Once the auth-add step is complete, you can submit jobs by running ::

 $ lava-tool submit-job http://user@example.com/lava-server/RPC2/
 jobfile.json

.. todo::
 Add link to information about constructing a job - lava-project might
 be a better place to put usage information in general
