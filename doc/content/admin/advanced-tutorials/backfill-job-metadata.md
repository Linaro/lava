# Backfilling job metadata

The [metadata](../../technical-references/job-metadata.md) of a job definition
is stored with the test job when the job is submitted, so that jobs can be
filtered by it. Jobs that were submitted before the instance was upgraded to
the LAVA version that introduced this feature have no metadata and are not
returned by any metadata filter.

The `backfill-metadata` sub command fills the metadata in from the definition
that is already stored with each job:

!!! example "Backfill job metadata"

    === "docker-compose"
        ```shell
        docker-compose exec lava-server lava-server manage jobs backfill-metadata
        ```

    === "debian"
        ```shell
        lava-server manage jobs backfill-metadata
        ```

Only the jobs with no metadata are considered, so the command can be
interrupted and started again. Jobs whose definition has no metadata are simply
skipped, at the cost of parsing their definition on every run.

The command parses one definition per job, which takes a while on instances
with a large number of jobs. Use `--start-id` and `--end-id` to split the work
into several runs, starting with the most recent jobs:

```shell
lava-server manage jobs backfill-metadata --start-id 900000
lava-server manage jobs backfill-metadata --start-id 800000 --end-id 899999
```

| Option         | Description                                          |
| -------------- | ---------------------------------------------------- |
| `--batch-size` | Number of jobs to update per query, 1000 by default   |
| `--start-id`   | First job id to consider                             |
| `--end-id`     | Last job id to consider                              |
| `--dry-run`    | Do not update the database, only report what would be |
| `--slow`       | Sleep between batches to reduce the load on the database |
