Description
============

Summary
#######

``lava-server`` is a command-line management interface to a LAVA instance,
and the Django database management tools for that instance.

Usage
#####

lava-server manage subcommand [options] [args]

Common Options
##############

Most of these options are imported from ``django`` and more
information can be found in the django documentation.

These options are supported for all subcommands.

  -v VERBOSITY, --verbosity=VERBOSITY
                        Verbosity level; 0=minimal output, 1=normal output,
                        2=verbose output, 3=very verbose output
  --settings=SETTINGS   The Python path to a settings module, e.g.
                        "myproject.settings.main". If this isn't provided, the
                        DJANGO_SETTINGS_MODULE environment variable will be
                        used.
  --pythonpath=PYTHONPATH
                        A directory to add to the Python path, e.g.
                        "/home/djangoprojects/myproject".
  --traceback           Print traceback on exception
  --version             show program's version number and exit
  -h, --help            show this help message and exit

Subcommands
###########

Type ``lava-server manage help <subcommand>`` for help on a specific subcommand.

Available subcommands
#####################

Type ``lava-server manage <subcommand> -h`` for help on an option available to
a specific subcommand.

auth
    changepassword
      Change a user's password for django.contrib.auth.

      Usage:
        lava-server manage changepassword [options]
      Options:
        --database=DATABASE   Specifies the database to use. Default is "default".

    createsuperuser
      Used to create a superuser.

      Usage:
        lava-server manage createsuperuser [options]
      Options:
        --username=USERNAME   Specifies the username for the superuser.
        --email=EMAIL         Specifies the email address for the superuser.
        --noinput             Tells Django to NOT prompt the user for input of any
                              kind. You must use ``--username`` and ``--email`` with
                              ``--noinput`` and superusers created with ``--noinput`` will
                              not be able to log in until they are given a valid
                              password.
        --database=DATABASE   Specifies the database to use. Default is **default**.

django

    django functions change with releases of the django package. See the
    documentation for python-django.

lava_scheduler_app

    devices
      Manage devices

      positional arguments:
        {add,details,list,set}
                              Sub commands
          add                 Add a device

            positional arguments:
              hostname              Hostname of the device

            optional arguments:
              -h, --help            show this help message and exit
              --device-type DEVICE_TYPE
                                    Device type
              --description DESCRIPTION
                                    Device description
              --dictionary DICTIONARY
                                    Device dictionary
              --non-pipeline        Create a v1 device (v2 by default)
              --offline             Create the device offline (online by default)
              --private             Make the device private (public by default)
              --worker WORKER       The name of the worker

          details             Details about a device

            positional arguments:
              hostname    Hostname of the device

          list                List the installed devices

            optional arguments:
              --all, -a             Show all devices, including retired ones
              --status {OFFLINE,IDLE,RUNNING,OFFLINING,RETIRED,RESERVED}
                                    Show only devices with this status
              --csv                 Print as csv

          set                 Set properties of the given device
            positional arguments:
              hostname              Hostname of the device

            optional arguments:
              -h, --help            show this help message and exit
              --description DESCRIPTION
                                    Set the description
              --dictionary DICTIONARY
                                    Device dictionary
              --public              make the device public
              --private             Make the device private
              --status {OFFLINE,IDLE,RUNNING,OFFLINING,RETIRED,RESERVED}
                                    Set the device status
              --health {UNKNOWN,PASS,FAIL,LOOPING}
                                    Set the device health status
              --worker WORKER       Set the worker

    device-types
      Manage device types according to which templates are available and which
      device-types are defined in the database. When counting the number of devices,
      Retired devices are included.

        positional arguments:
          {add,list}            Sub commands
            add                 Add V2 device type(s) to the database.

                positional arguments:
                  device-type           The device type name. Passing '*' will add all known
                                        V2 device types.

                optional arguments:
                  -h, --help            show this help message and exit

                health check:
                  Only supported when creating a single device-type

                  --health-check HEALTH_CHECK
                                        The health check (filename) for the given device type.
                  --health-frequency HEALTH_FREQUENCY
                                        How often to run health checks.
                  --health-denominator {hours,jobs}
                                        Initiate health checks by hours or by jobs.

            list                List the installed device types
                optional arguments:
                  -h, --help  show this help message and exit
                  --all, -a   Show all device types in the database, including non-installed
                              ones
                  --csv       Print as csv

    pipeline-worker

    LAVA Pipeline worker helper
            optional arguments:
          --hostname HOSTNAME   Hostname of the new worker
          --description DESCRIPTION
                                optional description of the new worker
          --disable             prevent pipeline jobs running on this worker.

    scheduler
      Run the LAVA test job scheduler

      Usage:
        lava-server manage scheduler [options]
      Options:
         --use-fake            Use fake dispatcher (for testing)
         --dispatcher=DISPATCHER
                             Dispatcher command to invoke

    schedulermonitor
     Run the LAVA test job scheduler

     Usage:
       lava-server manage schedulermonitor [options]

     Options:
       -l LOGLEVEL, --loglevel=LOGLEVEL
                        Log level, default is taken from settings.
       -f LOGFILE, --logfile=LOGFILE
                        Path to log file, default is taken from settings.

    test
      Runs the test suite for the specified applications, or the entire site if no apps are specified.

      Usage:
        lava-server manage test [options] [appname ...]
      Options:
          --noinput             Tells Django to NOT prompt the user for input of any
                                kind.
          --failfast            Tells Django to stop running the test suite after
                                first failed test.
          --testrunner=TESTRUNNER
                                Tells Django to use specified test runner class
                                instead of the one specified by the TEST_RUNNER
                                setting.
          --liveserver=LIVESERVER
                                Overrides the default address where the live server
                                (used with LiveServerTestCase) is expected to run
                                from. The default value is localhost:8081.

staticfiles
    collectstatic
      Collect static files in a single location.

      Usage:
        lava-server manage collectstatic [options]
      Options:
        --noinput             Do NOT prompt the user for input of any kind.
        --no-post-process     Do NOT post process collected files.
        -i PATTERN, --ignore=PATTERN
                        Ignore files or directories matching this glob-style
                        pattern. Use multiple times to ignore more.
        -n, --dry-run         Do everything except modify the filesystem.
        -c, --clear           Clear the existing files using the storage before
                        trying to copy or link the original file.
        -l, --link            Create a symbolic link to each file instead of
                        copying.
        --no-default-ignore   Don't ignore the common private glob-style patterns
                        ``'CVS'``, ``'.*'`` and ``'*~'``.

    findstatic
      Finds the absolute paths for the given static file(s).

      Usage:  lava-server manage findstatic [options] [file ...]

      Options:
      --first               Only return the first match for each static file.

    runserver
      Starts a lightweight Web server for development and also serves static files.

      Usage:
        lava-server manage runserver [options] [optional port number, or ipaddr:port]
      Options:
        -6, --ipv6            Tells Django to use a IPv6 address.
        --nothreading         Tells Django to NOT use threading.
        --noreload            Tells Django to NOT use the auto-reloader.
        --nostatic            Tells Django to NOT automatically serve static files
                        at STATIC_URL.
        --insecure            Allows serving static files even if DEBUG is False.

Bugs
####

If your bug relates to a specific type of device, please include all
configuration details for that device type as well as the job submission
JSON and as much of the LAVA test job log file as you can (e.g. as a compressed
file attached to the bug report).

If your device type is not one found on existing LAVA instances, please
supply as much information as you can on the board itself.

Contributing Upstream
#####################

If you, or anyone on your team, would like to register with Linaro directly,
this will allow you to file an upstream bug, submit code for review by
the LAVA team, etc. Register at the following url:

https://register.linaro.org/

If you are considering large changes, it is best to register and also
to subscribe to the Linaro Validation mailing list at:

http://lists.linaro.org/mailman/listinfo/linaro-validation

Also talk to us on IRC::

 irc.freenode.net
 #linaro-lava
