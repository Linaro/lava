# Timeouts

## Timeout syntax

A timeout is a dictionary with unit and value:

```yaml
timeout:
  <unit>: <value>
```

Valid units are `seconds`, `minutes`, `hours` and `days` while the value should be an integer.

## Job timeout

The entire job will have an overall timeout. The job will fail if this timeout
is exceeded, whether or not any other timeout is longer.

```yaml
timeouts:
  job:
    minutes: 15
```

## Action timeouts

Each action of a job will have a timeout. The action will not run longer than the
defined timeout.

### Job generic

In the job’s top-level `timeouts` block, you can set default action and individual
action timeouts.

#### Action timeout

Set the default duration of every action:

```yaml
timeouts:
  action:
    minutes: 5
```

#### Individual action timeout

Set the default duration of individual named action timeout:

```yaml
timeouts:
  actions:
    extract-nfsrootfs:
      minutes: 3
```

### Action block

You can define or override the job generic action timeouts in the action
definition block.

#### Action timeout

To define or override action timeout, you should add a `timeout` dictionary to
the action definition.

```yaml
actions:
- deploy:
    timeout:
      minutes: 5
    [...]
```

!!! warning "Action timeout"
    No action timeout can be larger than the job timeout. If the action timeout
    is larger than the job timeout, LAVA logs a warning and terminates the
    action when the job timeout is reached.

#### Individual action timeout

To define or override the individual named action timeout, you should
add a `timeouts` dictionary to the action definition.

```yaml
actions:
- deploy:
    timeout:
      minutes: 5
    timeouts:
      http-download:
        minutes: 1
```

### Repeatable action timeout

In order to have enough time to repeat or retry actions that have `repeat` or
`failure_retry` set (see [actions](./job.md#actions)), LAVA divides the timeout
by number of retries for each attempt.

For example:

```yaml
- boot:
   failure_retry: 4
   timeout:
     minutes: 20
```

This boot action will have a 5 minutes timeout for each of the 4 attempts. The
timeout can be further divided when a repeatable action is nested inside another
repeatable action.

### Timeout priority

Action timeout priority from lowest to highest:

1. [Job generic action timeout](#action-timeout)
2. Device individual action timeout
3. [Action block action timeout](#action-timeout_1)
4. [Repeatable action timeout](#repeatable-action-timeout)
5. [Job generic individual action timeout](#individual-action-timeout)
6. [Action block individual action timeout](#individual-action-timeout_1)

## Connection timeout

When an action interact with the DUT, this action will use the
`connection_timeout`. Each interaction with the DUT should take less than the
`connection_timeout` duration.

You can define the default duration of every connection timeout:

```yaml
timeouts:
  connection:
    seconds: 60
```

You can also define individual connection timeout in the root timeout dictionary:

```yaml
timeouts:
  connections:
    lava-test-shell:
      seconds: 60
```

## Queue timeout

You can specify how long the job can wait in the queue before it is
automatically canceled.

```yaml
timeouts:
  job:
    minutes: 60
  queue:
    hours: 72
```

## Skipping timeout

In some cases, a test action is known to hang or otherwise cause a timeout. If
the device is capable of booting again, then the first test action timeout can
set `skip: true` which stops the job finishing as `Incomplete` when the timeout
occurs. The job will then continue to the following `boot` actions, allowing the
device to reset to a known state and start the second test action. A second
`deploy` action might be also needed to get to a point where the device could
`boot` again.

```yaml hl_lines="4 8"
- test:
    timeout:
      minutes: 5
      skip: true
    definitions:
      [...]

- boot:
    timeout:
      minutes: 2
    [...]

- test:
    timeout:
      minutes: 5
    definitions:
      [...]
```

!!! note
    Skipping a test action timeout is intended for tests which may cause a
    kernel panic or other deadlock of the currently executing test shell. When a
    potential test timeout is expected, test writers should consider using
    utilities like the `timeout` command inside their own test shell scripts to
    retain control within the currently executing test shell scripts.
