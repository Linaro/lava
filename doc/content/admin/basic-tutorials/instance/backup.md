# Backup LAVA

In order to backup LAVA you will have to backup both the database and specific
directories.

## Database

### For a native Debian install
The database is managed by
[PostgreSQL](../../../technical-references/services/postgresql.md). See the
[PostgreSQL documentation][pgsql-backup] for
details.

To backup the database run:

```shell
sudo -u lavaserver pg_dump lavaserver > lava-server.sql
```

### For the docker-compose solution
If you run your LAVA instance with [docker-compose](https://git.lavasoftware.org/lava/pkg/docker-compose),
you can backup the database like this:
```shell
docker exec --user postgres docker-compose_db_1 bash -c \
            "pg_dump --username=lavaserver lavaserver > /tmp/lavaserver.sql"
```

On the host, you can then retrieve the backup file.
Example:
```shell
docker cp docker-compose_db_1:/tmp/lavaserver.sql .
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
