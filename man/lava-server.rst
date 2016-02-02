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
    cleanup
      Can be run as a cronjob or directly to clean out old data from the
      database (only expired sessions at the moment).

      Usage:
        lava-server manage cleanup [options]

    compilemessages
      Compiles .po files to .mo files for use with builtin gettext support.

      Usage:
        lava-server manage compilemessages [options]
      Options:
        -l LOCALE, --locale=LOCALE
                        The locale to process. Default is to process all.
    createcachetable
      Creates the table needed to use the SQL cache backend.

      Usage:
        lava-server manage createcachetable [options] <tablename>
      Options:
       --database=DATABASE   Nominates a database onto which the cache table will
                        be installed. Defaults to the "default" database.

    dbshell
      Runs the command-line client for specified database, or the default database if none is provided.

      Usage:
        lava-server manage dbshell [options]
      Options:
        --database=DATABASE   Nominates a database onto which to open a shell.
                        Defaults to the "default" database.

    diffsettings
      Displays differences between the current settings.py and the
      Django default settings. Settings that do not appear in the
      defaults are followed by "###".

      Usage:
        lava-server manage diffsettings [options]

    dumpdata
      Output the contents of the database as a fixture of the given
      format (using each model's default manager unless ``--all`` is specified).

      Usage:
        lava-server manage dumpdata [options] [appname appname.ModelName ...]

      Options:
        --format=FORMAT       Specifies the output serialization format for
                              fixtures.
        --indent=INDENT       Specifies the indent level to use when pretty-printing
                              output
        --database=DATABASE   Nominates a specific database to dump fixtures from.
                              Defaults to the "default" database.
        -e EXCLUDE, --exclude=EXCLUDE
                              An appname or appname.ModelName to exclude (use
                              multiple --exclude to exclude multiple apps/models).
        -n, --natural         Use natural keys if they are available.
        -a, --all             Use Django's base manager to dump all models stored in
                              the database, including those that would otherwise be
                              filtered or modified by a custom manager.

    flush
      Returns the database to the state it was in immediately after
      syncdb was executed. This means that all data will be removed from
      the database, any post-synchronization handlers will be re-executed
      and the initial_data fixture will be re-installed.

      Usage:
        lava-server manage flush [options]
      Options:
        --noinput             Tells Django to NOT prompt the user for input of any
                              kind.
        --database=DATABASE   Nominates a database to flush. Defaults to the
                              "default" database.

    inspectdb
      Introspects the database tables in the given database and outputs
      a Django model module.

      Usage:
        lava-server manage inspectdb [options]
      Options:
        --database=DATABASE   Nominates a database to introspect.  Defaults to using
                              the "default" database.

    loaddata
      Installs the named fixture(s) in the database.

      Usage:
        lava-server manage loaddata [options] fixture [fixture ...]

      Options:
        --database=DATABASE   Nominates a specific database to load fixtures into.
                        Defaults to the "default" database.


    makemessages
      Runs over the entire source tree of the current directory and
      pulls out all strings marked for translation. It creates (or
      updates) a message file in the conf/locale (in the django tree)
      or locale (for projects and applications) directory.

      Usage:
        lava-server manage makemessages [options]

      Options:
          -l LOCALE, --locale=LOCALE
                                Creates or updates the message files for the given
                                locale (e.g. pt_BR).
          -d DOMAIN, --domain=DOMAIN
                                The domain of the message files (default: "django").
          -a, --all             Updates the message files for all existing locales.
          -e EXTENSIONS, --extension=EXTENSIONS
                                The file extension(s) to examine (default: "html,txt",
                                or "js" if the domain is "djangojs"). Separate
                                multiple extensions with commas, or use -e multiple
                                times.
          -s, --symlinks        Follows symlinks to directories when examining source
                                code and templates for translation strings.
          -i PATTERN, --ignore=PATTERN
                                Ignore files or directories matching this glob-style
                                pattern. Use multiple times to ignore more.
          --no-default-ignore   Don't ignore the common glob-style patterns ``'CVS'``,
                                ``'.*'`` and ``'*~'``.
          --no-wrap             Don't break long message lines into several lines
          --no-location         Don't write '#: filename:line' lines
          --no-obsolete         Remove obsolete message strings

    reset
      Executes ``sqlreset`` for the given app(s) in the current database.

      Usage:
        lava-server manage reset [options] [appname ...]
      Options:
        --noinput             Tells Django to NOT prompt the user for input of any
                              kind.
        --database=DATABASE   Nominates a database to reset. Defaults to the
                              "default" database.

    runfcgi
      Run this project as a fastcgi (or some other protocol supported
      by flup) application. To do this, the flup package from
      http://www.saddi.com/software/flup/ is required.

      Usage:
       lava-server manage runfcgi [options] [fcgi settings]

      Options:
        See the django documentation for information on this option.

    shell
      Runs a Python interactive interpreter. Tries to use IPython, if it's available.

      Usage:
        lava-server manage shell [options]

      Options:
        --plain               Tells Django to use plain Python, not IPython.


    sql
      Prints the CREATE TABLE SQL statements for the given app name(s).

      Usage:
        lava-server manage sql [options] <appname appname ...>

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.


    sqlall
      Prints the CREATE TABLE, custom SQL and CREATE INDEX SQL statements
      for the given model module name(s).

      Usage:
        lava-server manage sqlall [options] <appname appname ...>

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.

    sqlclear
      Prints the DROP TABLE SQL statements for the given app name(s).

      Usage:
        lava-server manage sqlclear [options] <appname appname ...>

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.


    sqlcustom
      Prints the custom table modifying SQL statements for the given app name(s).

      Usage:
        lava-server manage sqlcustom [options] <appname appname ...>

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.

    sqlflush
      Returns a list of the SQL statements required to return all tables
      in the database to the state they were in just after they were installed.

      Usage:
        lava-server manage sqlflush [options]

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.

    sqlindexes
      Prints the CREATE INDEX SQL statements for the given model module name(s).

      Usage:
        lava-server manage sqlindexes [options] <appname appname ...>

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.

    sqlinitialdata
      RENAMED: see ``sqlcustom``

    sqlreset
      Prints the DROP TABLE SQL, then the CREATE TABLE SQL, for the given app name(s).

      Usage:
        lava-server manage sqlreset [options] <appname appname ...>

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.

    sqlsequencereset
      Prints the SQL statements for resetting sequences for the given app name(s).

      Usage:
        lava-server manage sqlsequencereset [options] <appname appname ...>

      Options:
        --database=DATABASE   Nominates a database to print the SQL for.
                              Defaults to the "default" database.
    startapp
      Creates a Django app directory structure for the given app name
      in the current directory or optionally in the given directory.

      Usage:
        lava-server manage startapp [options] [name] [optional destination directory]

      Options:
       --template=TEMPLATE   The dotted import path to load the template from.
       -e EXTENSIONS, --extension=EXTENSIONS
                        The file extension(s) to render (default: "py").
                        Separate multiple extensions with commas, or use -e
                        multiple times.
       -n FILES, --name=FILES
                        The file name(s) to render. Separate multiple
                        extensions with commas, or use -n multiple times.
    startproject
      Creates a Django project directory structure for the given project
      name in the current directory or optionally in the given directory.

      Usage:
        lava-server manage startproject [options] [name] [optional destination directory]

      Options:
       --template=TEMPLATE   The dotted import path to load the template from.
       -e EXTENSIONS, --extension=EXTENSIONS
                        The file extension(s) to render (default: "py").
                        Separate multiple extensions with commas, or use -e
                        multiple times.
       -n FILES, --name=FILES
                        The file name(s) to render. Separate multiple
                        extensions with commas, or use -n multiple times.

    validate
      Validates all installed models.

      Usage:
        lava-server manage validate [options]

django_openid_auth
    openid_cleanup
      Clean up stale OpenID associations and nonces

      Usage:
        lava-server manage openid_cleanup [options]

lava_scheduler_app
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

    testjobmigrate
      Fill out results_bundle on old testjobs.

      Usage:
        lava-server manage testjobmigrate [options]

    datamigration
      Creates a new template data migration for the given app

      Usage:
        lava-server manage datamigration [options]

      Options:
        --freeze=FREEZE_LIST  Freeze the specified app(s). Provide an app name with
                              each; use the option multiple times for multiple apps
        --stdout              Print the migration to stdout instead of writing it to
                              a file.

    graphmigrations
      Outputs a GraphViz dot file of all migration dependencies to stdout.

      Usage:
        lava-server manage graphmigrations [options]

    migrate
      Runs migrations for all apps.

      Usage:
        lava-server manage migrate [options] [appname]
        [migrationname|zero] [--all] [--list] [--skip] [--merge]
        [--no-initial-data] [--fake] [--db-dry-run] [--database=dbalias]

      Options:
          --all                 Run the specified migration for all apps.
          --list                List migrations noting those that have been applied
          --changes             List changes for migrations
          --skip                Will skip over out-of-order missing migrations
          --merge               Will run out-of-order missing migrations as they are -
                                no rollbacks.
          --no-initial-data     Skips loading initial data if specified.
          --fake                Pretends to do the migrations, but doesn't actually
                                execute them.
          --db-dry-run          Doesn't execute the SQL generated by the db methods,
                                and doesn't store a record that the migration(s)
                                occurred. Useful to test migrations before applying
                                them.
          --delete-ghost-migrations
                                Tells South to delete any 'ghost' migrations (ones in
                                the database but not on disk).
          --ignore-ghost-migrations
                                Tells South to ignore any 'ghost' migrations (ones in
                                the database but not on disk) and continue to apply
                                new migrations.
          --noinput             Tells Django to NOT prompt the user for input of any
                                kind.
          --database=DATABASE   Nominates a database to synchronize. Defaults to the
                                "default" database.

    migrationcheck
      Runs migrations for each app in turn, detecting missing depends_on values.

      Usage:
        lava-server manage migrationcheck [options]

    schemamigration
      Creates a new template schema migration for the given app

      Usage:
        lava-server manage schemamigration [options]
      Options:
          --freeze=FREEZE_LIST  Freeze the specified app(s). Provide an app name with
                                each; use the option multiple times for multiple apps
          --stdout              Print the migration to stdout instead of writing it to
                                a file.
          --add-model=ADDED_MODEL_LIST
                                Generate a Create Table migration for the specified
                                model.  Add multiple models to this migration with
                                subsequent --model parameters.
          --add-field=ADDED_FIELD_LIST
                                Generate an Add Column migration for the specified
                                modelname.fieldname - you can use this multiple times
                                to add more than one column.
          --add-index=ADDED_INDEX_LIST
                                Generate an Add Index migration for the specified
                                modelname.fieldname - you can use this multiple times
                                to add more than one column.
          --initial             Generate the initial schema for the app.
          --auto                Attempt to automatically detect differences from the
                                last migration.
          --empty               Make a blank migration.

    startmigration
      Deprecated command

    syncdb
      Create the database tables for all apps in INSTALLED_APPS whose
      tables have not already been created, except those which use
      migrations.

      Usage:
        lava-server manage syncdb [options]
      Options:
          --noinput             Tells Django to NOT prompt the user for input of any
                                kind.
          --database=DATABASE   Nominates a database to synchronize. Defaults to the
                                "default" database.
          --migrate             Tells South to also perform migrations after the sync.
                                Default for during testing, and other internal calls.
          --all                 Makes syncdb work on all apps, even migrated ones. Be
                                careful!

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

    testserver
      Runs a development server with data from the given fixture(s).

      Usage:
        lava-server manage testserver [options] [fixture ...]
      Options:
          --noinput             Tells Django to NOT prompt the user for input of any
                                kind.
          --addrport=ADDRPORT   port number or ipaddr:port to run the server on
          -6, --ipv6            Tells Django to use a IPv6 address.

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
