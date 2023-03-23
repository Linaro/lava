Description
============

Summary
#######

``lava-server`` is a command-line management interface to a LAVA instance, and
the Django database management tools for that instance.

Usage
#####

lava-server manage subcommand [options] [args]

Common Options
##############

Most of these options are imported from ``django`` and more information can be
found in the django documentation.

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
        --noinput             Tells Django to NOT prompt the user for input of
                              any kind. You must use ``--username`` and
                              ``--email`` with ``--noinput`` and superusers
                              created with ``--noinput`` will not be able to
                              log in until they are given a valid password.
        --database=DATABASE   Specifies the database to use. Default is **default**.

django

    django functions change with releases of the django package. See the
    documentation for python-django.

lava_server

    devices
      Manage devices

      positional arguments:
        {add, details, list, set}

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
              --offline             Create the device offline (online by default)
              --private             Make the device private (public by default)
              --worker WORKER       The name of the worker
              --tags [TAGS [TAGS ...]]
                                    List of tags to add to the device
              --physical-user PHYSICAL_USER
                                    Username of the user with physical access to the
                                    device
              --physical-group PHYSICAL_GROUP
                                    Name of the group with physical access to the device
              --owner OWNER         Username of the user with ownership of the device
              --group GROUP         Name of the group with ownership of the device

          copy                Copy an existing device as a new device

            positional arguments:
              original              Hostname of the existing device
              target                Hostname of the device to create

            optional arguments:
              -h, --help           show this help message and exit
              --offline            Create the device offline (online by default)
              --private            Make the device private (public by default)
              --worker WORKER      The name of the worker
              --copy-with-tags     Set all the tags of the original device on the target
                                   device

          details             Details about a device

            positional arguments:
              hostname    Hostname of the device

          list                List the installed devices

            optional arguments:
              -h, --help           show this help message and exit
              --state {IDLE,RESERVED,RUNNING}
                                   Show only devices with the given state
              --all, -a            Show all devices, including retired ones
              --health {GOOD,UNKNOWN,LOOPING,BAD,MAINTENANCE,RETIRED}
                                   Show only devices with the given health
              --csv                Print as csv
              --all, -a            Show all devices, including retired ones
              --status             {OFFLINE, IDLE, RUNNING, OFFLINING,
                                   RETIRED, RESERVED}
                                   Show only devices with this status
              --csv                Print as csv

          update              Update device details

            positional arguments:
              hostname             Hostname of the device

            optional arguments:
              -h, --help           show this help message and exit
              --description DESCRIPTION
                                   Set the description
              --health {GOOD,UNKNOWN,LOOPING,BAD,MAINTENANCE,RETIRED}
                                   Update the device health
              --worker WORKER      Update the worker
              --public             make the device public
              --private            Make the device private
              --physical-user PHYSICAL_USER
                                   Username of the user with physical access to the
                                   device
              --physical-group PHYSICAL_GROUP
                                   Name of the group with physical access to the device
              --owner OWNER        Username of the user with ownership of the device
              --group GROUP        Name of the group with ownership of the device

    device-types
      Manage device types according to which templates are available and which
      device-types are defined in the database. When counting the number of devices,
      Retired devices are included.

        positional arguments:
          {add, details, list, update}

        Sub commands
            add                 Add V2 device type(s) to the database.

                positional arguments:
                  device-type           The device type name. Passing '*' will add all known
                                        V2 device types.

                optional arguments:
                  -h, --help            show this help message and exit

                alias:
                  Only supported when creating a single device-type

                  --alias ALIAS         Name of an alias for this device-type.

                health check:
                  Only supported when creating a single device-type

                  --health-frequency HEALTH_FREQUENCY
                                        How often to run health checks.
                  --health-denominator  {hours, jobs}
                                        Initiate health checks by hours or by jobs.

            details             Details about a device-type

                positional arguments:
                  name        Name of the device-type

                optional arguments:
                  -h, --help  show this help message and exit
                  --devices   Print the corresponding devices

            list                List the installed device types
                optional arguments:
                  -h, --help  show this help message and exit
                  --all, -a   Show all device types in the database, including
                              types not currently installed.
                  --csv       Print as csv

            update              Update an existing V2 device type in the database
                positional arguments:
                  device-type    The device type name.

                optional arguments:
                  -h, --help     show this help message and exit

                alias:
                  --alias ALIAS  Name of an alias for this device-type.

    jobs
      Manage jobs

        positional arguments:
          {compress,fail,rm,validate}

        Sub commands
            compress            Compress job logs

                optional arguments:
                  -h, --help            show this help message and exit
                  --newer-than NEWER_THAN
                                        Compress jobs newer than this. The time is of the
                                        form: 1h (one hour) or 2d (two days). By default, all
                                        jobs will be compressed.
                  --older-than OLDER_THAN
                                        Compress jobs older than this. The time is of the
                                        form: 1h (one hour) or 2d (two days). By default, all
                                        jobs logs will be compressed.
                  --submitter SUBMITTER
                                        Filter jobs by submitter
                  --dry-run             Do not compress any logs, simulate the output
                  --slow                Be nice with the system by sleeping regularly

            fail                Fail the given canceled job

                positional arguments:
                  job_id      job id

                optional arguments:
                  -h, --help  show this help message and exit

            rm                  Remove the jobs

                optional arguments:
                  -h, --help            show this help message and exit
                  --older-than OLDER_THAN
                                        Remove jobs older than this. The time is of the form:
                                        1h (one hour) or 2d (two days). By default, all jobs
                                        will be removed.
                  --state {SUBMITTED,SCHEDULING,SCHEDULED,RUNNING,CANCELING,FINISHED}
                                        Filter by job state
                  --submitter SUBMITTER
                                        Filter jobs by submitter
                  --dry-run             Do not remove any data, simulate the output
                  --slow                Be nice with the system by sleeping regularly

            validate            Validate job definition

                optional arguments:
                  -h, --help            show this help message and exit
                  --mail-admins         Send a mail to the admins with a list of failing jobs
                  --submitter SUBMITTER
                                        Filter jobs by submitter
                  --newer-than NEWER_THAN
                                        Validate jobs newer than this. The time is of the
                                        form: 1h (one hour) or 2d (two days). By default, only
                                        jobs in the last 24 hours will be validated.
                  --strict              If set to True, the validator will reject any extra
                                        keys that are present in the job definition but not
                                        defined in the schema

    workers
      Manage workers

        position arguments:
          {add, details, list, update}

        Sub commands
            add                 Create a worker

                positional arguments:
                  hostname              Hostname of the worker

                optional arguments:
                  -h, --help            show this help message and exit
                  --description DESCRIPTION
                                        Worker description
                  --health {ACTIVE,MAINTENANCE,RETIRED}
                                        Worker health

            details             Details of a worker

                positional arguments:
                  hostname    Hostname of the worker

                optional arguments:
                  -h, --help  show this help message and exit
                  --devices   Print the list of attached devices


            list                List the workers

                optional arguments:
                  -h, --help  show this help message and exit
                  -a, --all   Show all workers (including retired ones)
                  --csv       Print as csv

            update              Update worker properties

                positional arguments:
                  hostname              Hostname of the worker

                optional arguments:
                  -h, --help            show this help message and exit
                  --description DESCRIPTION
                                        Worker description
                  --health {ACTIVE,MAINTENANCE,RETIRED}
                                        Set worker health

    test
      Runs the test suite for the specified applications, or the entire site
      if no apps are specified.

      Usage:
        lava-server manage test [options] [appname ...]
      Options:
          --noinput             Tells Django to NOT prompt the user for input
                                of any kind.
          --failfast            Tells Django to stop running the test suite after
                                first failed test.
          --testrunner TESTRUNNER
                                Tells Django to use specified test runner class
                                instead of the one specified by the TEST_RUNNER
                                setting.
          --liveserver LIVESERVER
                                Overrides the default address where the live server
                                (used with LiveServerTestCase) is expected to run
                                from. The default value is localhost:8081.

Bugs
####

If your bug relates to a specific type of device, please include all
configuration details for that device type as well as the job submission and as
much of the LAVA test job log file as you can (e.g. as a compressed file
attached to the bug report).

If your device type is not one found on existing LAVA instances, please
supply as much information as you can on the board itself.

Contributing Upstream
#####################

If you want to contribute, refer to https://docs.lavasoftware.org/lava/contribution.html

If you are considering large changes, it is best to subscribe to the Linaro
Validation mailing list at:

https://lists.lavasoftware.org/mailman3/lists/lava-users.lists.lavasoftware.org/

Also talk to us on IRC::

 irc.libera.chat
 #lavasoftware
