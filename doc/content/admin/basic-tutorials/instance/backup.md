# Backup LAVA

In order to backup LAVA you will have to backup both the database and specific
directories.

## Database

The database is managed by
[PostgreSQL](/technical-references/services/postgresql/). See the
[PostgreSQL documentation][pgsql-backup] for
details.

To backup the database run:

```shell
sudo -u lavaserver pg_dump lavaserver > lava-server.sql
```

## Filesystem

The configuration files are stored in:

* `/etc/lava-coordinator/`
* `/etc/lava-dispatcher/`
* `/etc/lava-server/`

The data (job outputs, ...) are stored in `/var/lib/lava-server/default/media`.

To backup the filesystem run:

```shell
tar czf lava-server-etc.tar.gz /etc/lava-coordinator/ \
                               /etc/lava-dispatcher/ \
                               /etc/lava-server/
tar czf lava-server-data.tar.gz /var/lib/lava-server/default/media/
```

--8<-- "refs.txt"
