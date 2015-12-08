.. index:: migrate-lava

LAVA Migrate Management Command
===============================

There is a management command known as `migrate-lava` which is
analogous to `django-admin migrate` command. The `migrate-lava`
command is a forked version of django upstream's `django-admin
migrate` command, except for the option `--db-dry-run`. The
`--db-dry-run` option does a dry-run of the migrations and prints the
SQL statements that will be executed as part of the migrations.

The SQL statements allow administrators to workaround issues when a
database migration times out during package installation. Admins can
apply the SQL directly through the psql command line to avoid the
timeouts, then fake the migration to complete the package
install. This is only necessary on very large data sets when a
migration modifies one of the largest tables, e.g. TestJob.

Most administrators will not need to use `migrate-lava` - it is
provided to assist in a limited number of instances.

.. caution:: Take great care using `migrate-lava` to apply database
             migrations directly using the SQL statements. Refer to
             the django documentation for detailed information on
             faking migrations.

See
https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-migrate
for details about `django-admin migrate`

This is inspired by the `--db-dry-run` option of south migrations as
explained in
http://south.readthedocs.org/en/latest/commands.html#options

There was a request in django upstream for this functionality
https://code.djangoproject.com/ticket/23347 which went through
discussion and the upstream decided to provide an alternate solution
such as `django-admin sqlmigrate` command as detailed in
https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-sqlmigrate

Though `django-admin sqlmigrate` command exists, at the current state
it lacks support for calculating pending migrations across all the
apps and providing the SQL statements for unmigrated apps.

For complete help on `migrate-lava` command, use the following::

  $ sudo lava-server manage migrate-lava --help
