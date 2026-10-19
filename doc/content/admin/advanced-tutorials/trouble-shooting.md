# How to find issues

When something is not working as expected, check the following areas.

## Logs

Each service writes its own log file:

| Service | Host | Log file |
| ------- | ---- | -------- |
| [lava-scheduler](../../technical-references/services/lava-scheduler.md) | server | `/var/log/lava-server/lava-scheduler.log` |
| [lava-server-gunicorn](../../technical-references/services/lava-server-gunicorn.md) | server | `/var/log/lava-server/gunicorn.log` and `/var/log/lava-server/django.log` |
| [lava-publisher](../../technical-references/services/lava-publisher.md) | server | `/var/log/lava-server/lava-publisher.log` |
| [lava-celery-worker](../../technical-references/services/lava-celery-worker.md) | server | `/var/log/lava-server/lava-celery-worker.log` |
| [apache2](../../technical-references/services/apache2.md) | server | `/var/log/apache2/lava-server.log` |
| [lava-coordinator](../../technical-references/services/lava-coordinator.md) | server | `/var/log/lava-coordinator.log` |
| [lava-worker](../../technical-references/services/lava-worker.md) | worker | `/var/log/lava-dispatcher/lava-worker.log` |

The log files are rotated by `logrotate`: older logs are in `.1` or `.gz`
files. Use `zless` or `zgrep` to read them.

To get more details, set `LOGLEVEL="DEBUG"` in the daemon start options (for
instance `/etc/lava-server/lava-scheduler` or `/etc/lava-dispatcher/lava-worker`)
and restart the service.

Crashes of the services are logged with a Python traceback in these files.

## Job logs

The job log is displayed in the job page. On the server, the job files are
stored in
`/var/lib/lava-server/default/media/job-output/<year>/<month>/<day>/<job id>/`
where the date is the submit date:

* `output.yaml`: the job log
* `description.yaml`: the job pipeline, as described by the worker

Start with the failure comment and the error type at the top of the job page,
then look for the first error in the job log. The error type tells who should
fix the issue:

* `Infrastructure`: an issue with the LAVA infrastructure (PDU, serial
  connection, network...). The admins should look at it.
* `Configuration`: an issue with the device or dispatcher configuration.
* `Job`: an issue with the job definition or the files used by the job.
* `Test`: an issue in the tests.
* `LAVATimeout`: an action timed out.
* `Bug`: an issue in LAVA. Please [report it](https://gitlab.com/lava/lava/-/issues).

### Reproducing a job on the worker

A job can be run directly on the worker, without the server, with `lava-run`.

Get the device configuration with [lavacli](../../user/basic-tutorials/lavacli.md):

```shell
lavacli devices dict get --render <hostname> > device.yaml
```

Then run the job:

```shell
sudo lava-run --job-id 0 --device device.yaml --output-dir /tmp/debug/ job.yaml
```

Add `--validate` to only validate the job and save the pipeline into
`description.yaml`, without running it.

!!! warning
    Put the device in *Maintenance* before running a job manually, otherwise
    the scheduler can start a job on the same device.

## Jobs stay in the queue

A job stays *Submitted* while no device can run it. The
[scheduler](../../technical-references/state-machine.md#scheduler) only
considers devices that are:

* *Idle*
* *Good* or *Unknown*
* attached to an *Online* and *Active* worker

Check, in this order:

1. **The worker is *Offline***: the worker has not pinged the server for 60
   seconds. Check that the `lava-worker` service is running and look at its
   logs. A worker running a different LAVA version than the server is kept
   *Offline*: upgrade the worker, or set `ALLOW_VERSION_MISMATCH: true` in the
   server [settings](../basic-tutorials/instance/configure.md).
2. **The worker is in *Maintenance***: set it back to *Active*:
   ```shell
   lava-server manage workers update <hostname> --health ACTIVE
   ```
3. **The devices are *Bad*, in *Maintenance* or *Retired***. A device is set
   to *Bad* when its health-check fails or when its configuration is invalid.
   Check the configuration with:
   ```shell
   lava-server manage devices check <hostname>
   ```
4. **The devices are running health-checks**: when the device type has a
   health-check, a device in *Unknown* or *Looping* health runs a health-check
   before any other job.
5. **The job requirements**: the job can request [tags](../../technical-references/job-definition/job.md#tags),
   a specific device or a specific worker. The submitter should also be allowed
   to submit to the device.
6. **The worker job limit**: when the worker `job_limit` is set, the scheduler
   does not start more jobs on this worker.
7. **MultiNode jobs**: a MultiNode job starts when every sub job has a device.
   The sub jobs that already have a device stay in *Scheduling*, keeping the
   device *Reserved*.

Set the scheduler logs to `DEBUG` to see the decisions of the scheduler.

## Jobs not terminating

When a job is canceled, it goes to *Canceling* and the worker is asked to stop
the job. If the job does not stop, the worker sends a second signal and then
kills it. Look at the worker logs for this job id.

A job stays in *Canceling* when the worker is *Offline*. Fix the worker first:
when coming back, the worker will finish the job.

If the worker cannot be fixed, a superuser can force the job to *Incomplete*
with the **Fail** button on the job page, or with:

```shell
lava-server manage jobs fail <job id>
```

!!! warning
    This only updates the database: a `lava-run` process still running on the
    worker is not stopped.

## MultiNode issues

* Every worker should have `/etc/lava-coordinator/lava-coordinator.conf`
  pointing to the same [lava-coordinator](../../technical-references/services/lava-coordinator.md).
* Check the coordinator logs in `/var/log/lava-coordinator.log`.
* Restarting `lava-coordinator` breaks all running MultiNode jobs.

## Performances

* Remove old jobs and their logs:
  ```shell
  lava-server manage jobs rm --older-than 180d --slow
  ```
  Use `--dry-run` to check what will be removed and `--logs-only` to keep the
  jobs in the database.
* Increase the number of gunicorn `WORKERS` in
  `/etc/lava-server/lava-server-gunicorn`.
* Limit the number of jobs running at the same time on a worker with
  `job_limit`.
* Store the job logs in a [database](logging-database.md).
