# Health Checks

See [health checks](../../technical-references/configuration/health-check.md) for
adding device health checks.

[Notifications](../../technical-references/job-definition/notifications.md) should
be enabled to ensure administrators are alerted when health checks fail.

A failing health check takes the device offline, so avoid intermittent
failures that are not caused by the device. On Linux devices, set
[`lava-signal: kmsg`](../../technical-references/job-definition/actions/test.md#lava-signal)
on the test definitions so that a kernel message printed at the wrong time
can't corrupt a LAVA signal. See
[kernel messages corrupting LAVA signals](../../user/advanced-tutorials/debugging-job.md#kernel-messages-corrupting-lava-signals).
