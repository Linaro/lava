# LAVA logs in database

LAVA logs are received and stored by lava-server-gunicorn. The default
storage backend uses filesystem for storing logs and the default location of
`/var/lib/lava-server/default/media/job-output/`.

LAVA also supports storing the logs in a few NoSQL based database engines.

## Configuration

This can be set up in the [LAVA configuration](../basic-tutorials/instance/configure.md), like so:

```yaml
LAVA_LOG_BACKEND: "lava_scheduler_app.logutils.LogsFilesystem"
```

Available backends are:

* `lava_scheduler_app.logutils.LogsMongo`
* `lava_scheduler_app.logutils.LogsElasticsearch`
* `lava_scheduler_app.logutils.LogsFirestore`

The list can be also found in [the source code](https://git.lavasoftware.org/lava/lava/-/blob/master/lava_server/settings/common.py)

### MongoDB

Integration with MongoDB requires two variables to be set in the [LAVA settings](../basic-tutorials/instance/configure.md):

* `MONGO_DB_URI` - connection string URI format for mongodb (i.e. mongodb://example.com:27017)
* `MONGO_DB_DATABASE` - database name for LAVA logs (i.e. 'lava-logs')

Every log line in LAVA is one document in MongoDB database.

### ElasticSearch

Integration with Elasticsearch db requires three variables to be set in the [LAVA settings](../basic-tutorials/instance/configure.md):

* `ELASTICSEARCH_URI` - connection string URI format for Elasticsearch (i.e. http://localhost:9200/)
* `ELASTICSEARCH_INDEX` - database(index) name for LAVA logs (i.e. 'lava-logs')
* `ELASTICSEARCH_APIKEY` - API key to be used in Authorization header when
  sending requests to the Elasticsearch API. Can be obtained via [this request](https://www.elastic.co/guide/en/elasticsearch/reference/current/security-api-create-api-key.html).

Every log line in LAVA is one document in Elasticsearch database.

### Firestore

Still proof of concept, does not cover full integration with LAVA logs.
Patches are welcome.

In order to user Google firestore, you first have to create a project and
generate a private key file for the service account [here](https://console.firebase.google.com/project/_/settings/serviceaccounts/adminsdk).

The root collection is currently hardcoded to `logs`.

Firestore integration does not currently support limited read for each job,
meaning that incremental read on the job UI will not work properly.

## Log database migration

If the logging database is used from the very first installation of one LAVA
instance then all the logs will be stored in the said database, but if the
switch is made at one later point in the life of a LAVA instance, then you
can use the management command [copy-logs](https://git.lavasoftware.org/lava/lava/-/blob/master/lava_server/management/commands/copy-logs.py) to copy the logs
from the filesystem to the database of your choosing.
It is mandatory to have appropriate configuration variables set in LAVA settings in order to properly connect to the database.

!!! example "From filesystem to MongoDB"

    ```shell
    lava-server manage copy-logs LogsMongo
    ```

!!! example "From filesystel to ElasticSearch"

    ```shell
    lava-server manage copy-logs --dry-run LogsElasticsearch
    ```

!!! warning "copy-logs compatibility"
    Management command `copy-logs` is only applicable to the MongoDB and
    Elasticsearch database engines. Firestore is not yet supported.

